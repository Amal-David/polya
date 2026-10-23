import json
import logging
import re

import pytest

pytest.importorskip('mcp')
from starlette.testclient import TestClient
from deploy.server import create_app

TOKEN = 'test-only-polya-token-with-32-characters'
HEADERS = {'Authorization': f'Bearer {TOKEN}', 'Accept': 'application/json, text/event-stream'}


@pytest.fixture
def client():
    with TestClient(create_app(TOKEN, 'https://testserver')) as client:
        yield client


def rpc(client, method, params=None):
    return client.post('/mcp', headers=HEADERS,
                       json={'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params or {}})


def test_remote_contract_and_exact_execution(client):
    init = rpc(client, 'initialize', {'protocolVersion': '2025-06-18',
                                     'capabilities': {}, 'clientInfo': {'name': 'test', 'version': '1'}})
    assert init.status_code == 200
    assert init.json()['result']['serverInfo']['name'] == 'polya'
    tools = rpc(client, 'tools/list').json()['result']['tools']
    assert [tool['name'] for tool in tools] == ['puzzle.find', 'puzzle.run']
    contract = rpc(client, 'tools/call', {'name': 'puzzle.find',
                                        'arguments': {'operation_id': 'cipher.polyalphabetic'}})
    assert not contract.json()['result']['isError']
    result = rpc(client, 'tools/call', {'name': 'puzzle.run', 'arguments': {
        'operation_id': 'cipher.polyalphabetic',
        'inputs': {'text': 'LXFOPVEFRNHR', 'key': 'LEMON', 'variant': 'vigenere'},
    }}).json()['result']
    assert not result['isError']
    assert result['structuredContent']['data']['result']['text'] == 'ATTACKATDAWN'
    bad = rpc(client, 'tools/call', {'name': 'puzzle.run', 'arguments': {
        'operation_id': 'bytes.decode', 'inputs': {'encoding': 'hex', 'value': 'bad'},
    }}).json()['result']
    assert bad['isError'] and 'No puzzle hypothesis' in bad['content'][0]['text']


def test_authentication_and_host_boundaries(client):
    assert client.get('/healthz').status_code == 200
    assert client.post('/mcp', json={}).status_code == 401
    assert client.post('/mcp', headers={'Authorization': 'Bearer wrong'}, json={}).status_code == 401
    assert client.post('/mcp?api_key=wrong', json={}).status_code == 401
    assert client.post(f'/mcp?api_key={TOKEN}&api_key={TOKEN}', json={}).status_code == 401
    assert client.post('/mcp', headers=[('Authorization', f'Bearer {TOKEN}'),
                                      ('Authorization', f'Bearer {TOKEN}')], json={}).status_code == 401
    keyed = client.post(f'/mcp?api_key={TOKEN}', headers={'Accept': HEADERS['Accept']},
                        json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'})
    assert keyed.status_code == 200 and len(keyed.json()['result']['tools']) == 2
    assert client.post('/mcp', headers={**HEADERS, 'Host': 'evil.example'}, json={}).status_code == 421
    assert client.post('/mcp', headers={**HEADERS, 'Origin': 'https://evil.example'}, json={}).status_code == 403
    assert client.post('/mcp/', follow_redirects=False, json={}).status_code == 404


def test_request_budget_and_missing_secret_fail_closed(client):
    assert client.post('/mcp', headers={**HEADERS, 'Content-Type': 'application/json'},
                       content=b' ' * 1_000_001).status_code == 413
    with pytest.raises(ValueError, match='at least 32'):
        create_app('', 'https://testserver')


def tool_events(caplog):
    return [json.loads(record.message) for record in caplog.records
            if record.message.startswith('{"event":"polya.tool_call"')]


def test_tool_event_correlates_receipt_without_payloads(client, caplog):
    caplog.set_level(logging.INFO, logger='uvicorn.error')
    private_text = 'synthetic-private-input-do-not-log'
    result = rpc(client, 'tools/call', {'name': 'puzzle.run', 'arguments': {
        'operation_id': 'text.profile', 'inputs': {'text': private_text},
    }}).json()['result']
    event, = tool_events(caplog)
    assert not result['isError']
    assert event['execution_id'] == result['_meta']['polya/execution_id']
    assert re.fullmatch('[0-9a-f]{32}', event['execution_id'])
    assert event['operation_id'] == 'text.profile' and event['outcome'] == 'ok'
    assert event['elapsed_ms'] >= 0
    assert set(event) == {'event', 'execution_id', 'tool', 'operation_id', 'outcome',
                          'elapsed_ms', 'queue_ms', 'execution_ms', 'serialization_ms', 'version', 'revision'}
    serialized = json.dumps(event)
    assert private_text not in serialized and TOKEN not in serialized
    assert result['structuredContent']['data']['receipt']['inputs_sha256'] not in serialized


def test_tool_errors_are_logged_without_exception_or_unknown_operation_text(client, caplog):
    caplog.set_level(logging.INFO, logger='uvicorn.error')
    private_id = 'synthetic-private-operation-do-not-log'
    result = rpc(client, 'tools/call', {'name': 'puzzle.run', 'arguments': {
        'operation_id': private_id, 'inputs': {},
    }}).json()['result']
    event, = tool_events(caplog)
    assert result['isError'] and event['outcome'] == 'tool_error'
    assert event['operation_id'] is None
    assert event['execution_id'] == result['_meta']['polya/execution_id']
    assert private_id not in json.dumps(event)


def test_discovery_query_is_not_logged_and_execution_ids_are_distinct(client, caplog):
    caplog.set_level(logging.INFO, logger='uvicorn.error')
    for _ in range(2):
        result = rpc(client, 'tools/call', {'name': 'puzzle.find', 'arguments': {
            'query': 'synthetic-private-query-do-not-log',
        }}).json()['result']
        assert not result['isError']
    first, second = tool_events(caplog)
    assert first['execution_id'] != second['execution_id']
    assert first['operation_id'] is None
    assert 'synthetic-private-query-do-not-log' not in json.dumps([first, second])


def test_health_revision_is_exact_and_never_arbitrary_environment_text(client, monkeypatch):
    monkeypatch.setenv('RENDER_GIT_COMMIT', 'a' * 40)
    assert client.get('/healthz').json()['revision'] == 'a' * 40
    monkeypatch.setenv('RENDER_GIT_COMMIT', 'synthetic-secret-not-a-revision')
    assert client.get('/healthz').json()['revision'] is None
    monkeypatch.delenv('RENDER_GIT_COMMIT')
    assert client.get('/healthz').json()['revision'] is None


@pytest.mark.parametrize('failure_kind', ['output_limit', 'protocol_error', 'internal_error'])
def test_adapter_failures_keep_bounded_correlated_error(client, caplog, monkeypatch, failure_kind):
    from deploy.server import Server

    def fail(self, message):
        if failure_kind == 'internal_error':
            raise RuntimeError('synthetic-private-exception-do-not-log')
        if failure_kind == 'protocol_error':
            return {'error': {'message': 'synthetic-private-error-do-not-log'}}
        return {'result': {'isError': False, 'content': [
            {'type': 'text', 'text': 'x' * 2_200_001}]}}

    monkeypatch.setattr(Server, 'handle', fail)
    caplog.set_level(logging.INFO, logger='uvicorn.error')
    result = rpc(client, 'tools/call', {'name': 'puzzle.run', 'arguments': {
        'operation_id': 'text.profile', 'inputs': {'text': 'abc'},
    }}).json()['result']
    event, = tool_events(caplog)
    assert result['isError'] and event['outcome'] == failure_kind
    assert result['_meta']['polya/execution_id'] == event['execution_id']
    assert len(json.dumps(result)) < 1000
    assert 'No puzzle hypothesis' in result['content'][0]['text']
    assert 'synthetic-private' not in json.dumps(event) + json.dumps(result)


def test_all_captured_application_logs_omit_request_secrets(client, caplog):
    caplog.set_level(logging.DEBUG)
    private = 'synthetic-private-app-record-8675309'
    for tool, arguments in [
        ('puzzle.find', {'query': private}),
        ('puzzle.run', {'operation_id': 'text.profile', 'inputs': {'text': private}}),
        ('puzzle.run', {'operation_id': private, 'inputs': {}}),
        (private, {}),
    ]:
        rpc(client, 'tools/call', {'name': tool, 'arguments': arguments})
    client.post('/mcp', headers={**HEADERS, 'Host': private}, json={})
    client.post('/mcp', headers={**HEADERS, 'Origin': 'https://' + private}, json={})
    records = [record for record in caplog.records
               if record.name.startswith(('mcp.', 'uvicorn.'))]
    assert records
    for record in records:
        assert private not in record.getMessage()
        assert TOKEN not in record.getMessage()
        assert record.exc_info is None and record.stack_info is None


def test_worker_concurrency_stays_one_and_queue_metrics_are_separate(client, caplog, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    import time
    from deploy.server import Server

    original = Server.handle
    lock = threading.Lock()
    active = maximum = 0

    def slow(self, message):
        nonlocal active, maximum
        with lock:
            active += 1
            maximum = max(maximum, active)
        try:
            time.sleep(0.02)  # Synthetic work, never a performance assertion.
            return original(self, message)
        finally:
            with lock:
                active -= 1

    monkeypatch.setattr(Server, 'handle', slow)
    caplog.set_level(logging.INFO, logger='uvicorn.error')
    with ThreadPoolExecutor(max_workers=3) as pool:
        replies = list(pool.map(lambda _: rpc(client, 'tools/call', {'name': 'puzzle.run',
            'arguments': {'operation_id': 'text.profile', 'inputs': {'text': 'abc'}}}), range(3)))
    assert maximum == 1 and all(not r.json()['result']['isError'] for r in replies)
    events = tool_events(caplog)
    assert len(events) == 3
    for event in events:
        assert event['queue_ms'] >= 0 and event['execution_ms'] >= 0
        assert event['serialization_ms'] >= 0
        assert event['elapsed_ms'] + 0.01 >= event['queue_ms'] + event['execution_ms']
