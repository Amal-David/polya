import json
import subprocess
import sys
from polya.mcp_server import Server
from polya.session import Session


def request(method,id=1,params=None): return {'jsonrpc':'2.0','id':id,'method':method,'params':params or {}}
def ready():
    s=Server();s.handle(request('initialize',params={'protocolVersion':'2025-06-18'}))
    assert s.handle({'jsonrpc':'2.0','method':'notifications/initialized'}) is None
    return s


def test_mcp_handshake_tools_and_structured_result():
    s=Server(); assert s.handle(request('tools/list'))['error']['code']==-32002
    r=s.handle(request('initialize',params={'protocolVersion':'2025-06-18'}))
    assert r['result']['protocolVersion']=='2025-06-18'
    s.handle({'jsonrpc':'2.0','method':'notifications/initialized'})
    assert len(s.handle(request('tools/list'))['result']['tools'])==2
    r=s.handle(request('tools/call',params={'name':'puzzle.run','arguments':{'operation_id':'automata.from_runs','inputs':{'runs':[2]}}}))
    assert not r['result']['isError'] and r['result']['structuredContent']['data']['result']['machine']['kind']=='dfa'


def test_mcp_bad_calls_are_not_puzzle_negatives():
    s=ready()
    assert s.handle(request('tools/call',params={'name':'shell'}))['error']['code']==-32602
    r=s.handle(request('tools/call',params={'name':'puzzle.run','arguments':{'operation_id':'bytes.decode','inputs':{'encoding':'hex','value':'bad'}}}))
    assert r['result']['isError'] and 'No puzzle hypothesis' in r['result']['content'][0]['text']
    assert s.handle(request('unknown'))['error']['code']==-32601
    assert s.handle([])['error']['code']==-32600


def test_real_stdio_process_roundtrip():
    messages=[request('initialize',params={'protocolVersion':'2025-06-18'}),
              {'jsonrpc':'2.0','method':'notifications/initialized'},request('tools/list',2),
              request('tools/call',3,{'name':'puzzle.run','arguments':{'operation_id':'symbolic.analyze','inputs':{
                  'model':{'variables':{'x':{'values':[3]}}},'backend':'reference'}}})]
    p=subprocess.run([sys.executable,'-m','polya','mcp'],input='\n'.join(map(json.dumps,messages))+'\n',
                     text=True,capture_output=True,timeout=15)
    assert p.returncode==0 and p.stderr==''
    replies=[json.loads(line) for line in p.stdout.splitlines()]
    assert [r['id'] for r in replies]==[1,2,3]
    assert replies[0]['result']['serverInfo']['name']=='polya'
    assert replies[-1]['result']['structuredContent']['data']['result']['uniqueness']=='UNIQUE'


def test_budgeted_calls_never_become_cached_evidence():
    args={'model':{'variables':{'x':{'lower':0,'upper':1}}},'backend':'reference','max_checks':1}
    with Session(':memory:') as session:
        first=session.run('symbolic.solve',args);second=session.run('symbolic.solve',args)
        assert not first['cache_hit'] and not second['cache_hit']
        assert not second['result']['complete']
        assert not second['receipt']['independently_reproduced']
        assert session.connection.execute('SELECT count(*) FROM results').fetchone()[0]==0


def test_strict_external_json_rejects_duplicates_and_nonfinite_numbers():
    import pytest
    from polya.jsonio import loads
    for raw in ['{"x":1,"x":2}','{"nested":{"x":1,"x":2}}','{"x":NaN}','{"x":Infinity}']:
        with pytest.raises(ValueError): loads(raw)
    p=subprocess.run([sys.executable,'-m','polya','run','text.profile','--input','-'],
                     input='{"text":"a","text":"b"}',text=True,capture_output=True,timeout=10)
    assert p.returncode==2 and json.loads(p.stderr)['execution_status']=='ERROR'
