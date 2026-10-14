import pytest
from polya.ledger import Ledger


def test_persistent_retraction_reaches_transitive_dependents(tmp_path):
    db=str(tmp_path/'case.sqlite')
    with Ledger(db) as log:
        a=log.append('observation',{'glyph':'3'})
        b=log.append('hypothesis',{'meaning':'index'},dependencies=[a])
        c=log.append('experiment',{'status':'UNKNOWN'},dependencies=[b])
        d=log.append('observation',{'independent':'not retracted'})
    with Ledger(db) as log:
        log.append('retraction',{'reason':'original image shows 8'},retracts=a)
        statuses={e['id']:e['review_status'] for e in log.snapshot()['events']}
        assert statuses[a]=='RETRACTED'
        assert statuses[b]==statuses[c]=='REVIEW_REQUIRED'
        assert statuses[d]=='RECORDED'
        assert not log.snapshot()['authenticated']
        assert len(log.events())==5


def test_events_are_detached_and_bad_dependencies_rollback():
    with Ledger(':memory:') as log:
        payload={'text':'original'};a=log.append('observation',payload);payload['text']='changed'
        assert log.events()[0]['payload']['text']=='original'
        with pytest.raises(ValueError): log.append('hypothesis',{},dependencies=['missing'])
        assert len(log.events())==1
        with pytest.raises(ValueError): log.append('observation',{},retracts=a)
        log.append('review',{},dependencies=[a])
        assert len(log.events())==2


def test_detects_edited_body_and_hash_chain():
    with Ledger(':memory:') as log:
        log.append('observation',{'x':1})
        log.connection.execute("UPDATE evidence_events SET body=replace(body,'\"x\":1','\"x\":2')")
        log.connection.commit()
        with pytest.raises(ValueError,match='integrity'): log.snapshot()
        with pytest.raises(ValueError): log.append('review',{})
