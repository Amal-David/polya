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
