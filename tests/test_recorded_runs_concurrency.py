"""Independent workspace owners publish readable records during concurrent writes."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from polya import catalog
from polya.ledger import Ledger
from polya.workspace import Workspace


def test_independent_workspaces_record_and_read_concurrently(tmp_path):
    texts = ['Résumé', 'A\x00B', 'λ']
    workers = 4
    rendezvous = Barrier(workers)
    # Complete runtime discovery before workers start so this test isolates
    # persistence, rather than an optional backend's first import transition.
    catalog.prepare('text.encode', {'text': texts[0], 'codec': 'utf-8'})

    def record_all(_):
        records = []
        with Workspace(tmp_path) as workspace:
            for text in texts:
                rendezvous.wait(timeout=20)
                result = workspace.run_recorded('text.encode', {
                    'text': text, 'codec': 'utf-8',
                })
                # Read while other owners may still be appending: a valid event
                # must already have both durable artifacts and its index entry.
                saved = workspace.load_recorded(result['ledger_event_id'])
                assert saved['inputs'] == {'text': text, 'codec': 'utf-8'}
                assert saved['envelope']['result']['hex'] == text.encode('utf-8').hex()
                assert saved['review_status'] == 'RECORDED'
                records.append(result)
        return records

    with ThreadPoolExecutor(max_workers=workers) as pool:
        records = [record for group in pool.map(record_all, range(workers)) for record in group]

    ids = [record['ledger_event_id'] for record in records]
    assert len(ids) == workers * len(texts)
    assert len(set(ids)) == len(ids)
    # Identical content deduplicates, but every actual execution has its own
    # event. Sharing artifacts must never collapse execution history.
    assert len({record['request_ref'] for record in records}) == len(texts)
    assert len({record['response_ref'] for record in records}) == len(texts)
    with Ledger(tmp_path / 'history.sqlite') as ledger:
        events = ledger.snapshot()['events']
        assert {event['id'] for event in events} == set(ids)
        assert all(event['review_status'] == 'RECORDED' for event in events)
    with Workspace(tmp_path) as reopened:
        for event_id in ids:
            record = reopened.load_recorded(event_id)
            assert record['envelope']['result']['hex'] == record['inputs']['text'].encode('utf-8').hex()
            assert record['independently_reproduced'] is False
