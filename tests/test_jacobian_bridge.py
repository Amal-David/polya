"""Contract and adversarial transport tests with a deterministic Jacobian-shaped MCP host.

The mock is not claimed as upstream integration. Actual upstream is a separate job.
"""
from __future__ import annotations

import os
from pathlib import Path
import stat
import sys
import textwrap
import time
from unittest.mock import patch

import pytest

from polya import find, run
from polya.jacobian_bridge import find_math, inspect_runtime, pin, run_math

MOCK = '''#!{python}
import json, os, sys, time
mode=os.environ.get('FAKE_JACOBIAN_MODE','ok')
for raw in sys.stdin.buffer:
    req=json.loads(raw)
    if req.get('method')=='initialize':
        if mode=='hang': time.sleep(60)
        name='other' if mode=='impostor' else 'jacobian'
        version='0.0.0' if mode=='version' else '0.23.0'
        result={{'jsonrpc':'2.0','id':1,'result':{{'protocolVersion':'2025-06-18',
           'serverInfo':{{'name':name,'version':version}},'capabilities':{{'tools':{{}}}}}}}}
    elif req.get('method')=='notifications/initialized':
        continue
    elif req.get('method')=='tools/call':
        tool=req['params']['name'];args=req['params']['arguments']
        if mode=='upstream_error':
            result={{'jsonrpc':'2.0','id':2,'result':{{'isError':True,'content':[{{'type':'text',
             'text':json.dumps({{'code':'INVALID_REQUEST','stage':'operation_validation'}})}}]}}}}
        elif tool=='math.find':
            if 'query' in args:
                data={{'kind':'matches','need':args['query'],'total_matches':1,
                       'matches':[{{'operation_id':'integer.compute.extended_gcd','title':'GCD'}}]}}
            else:
                data={{'kind':'operation','operation':{{'operation_id':args['operation_id'],
                     'input_schema':{{'type':'object'}}}},'backend_availability':[]}}
            result={{'jsonrpc':'2.0','id':2,'result':{{'content':[{{'type':'text',
                 'text':json.dumps(data)}}],'structuredContent':data}}}}
        else:
            data={{'operation_id':args['operation_id'],'runtime_ms':10,'output':{{'gcd':'6'}}}}
            result={{'jsonrpc':'2.0','id':2,'result':{{'content':[{{'type':'text',
                 'text':json.dumps(data)}}],'structuredContent':data, 'isError':False}}}}
        if mode=='bad_output': result['result']['structuredContent']={{'unexpected':True}}
    else:
        continue
    if mode=='oversize' and req.get('id')==2:
        sys.stdout.write('x'*1100001+'\\n');sys.stdout.flush();continue
    sys.stdout.write(json.dumps(result,separators=(',',':'))+'\\n');sys.stdout.flush()
'''


@pytest.fixture
def fake_backend(tmp_path, monkeypatch):
    # Windows cannot CreateProcess an extensionless Python shebang. Use a
    # trusted .cmd test shim there, while production uses jacobian-mcp.exe.
    if os.name == 'nt':
        script = tmp_path / 'fake_jacobian.py'
        script.write_text(MOCK.format(python=sys.executable), encoding='utf-8')
        file = tmp_path / 'jacobian-mcp.cmd'
        file.write_text(
            '@echo off\n'
            'if "%FAKE_JACOBIAN_MODE%"=="hang" goto hang\n'
            f'"{sys.executable}" "{script}"\n'
            'exit /b 0\n'
            ':hang\n'
            'goto hang\n', encoding='utf-8')
    else:
        file = tmp_path / 'jacobian-mcp'
        file.write_text(MOCK.format(python=sys.executable), encoding='utf-8')
        file.chmod(file.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv('POLYA_JACOBIAN_MCP', str(file))
    monkeypatch.delenv('FAKE_JACOBIAN_MODE', raising=False)
    return file


def test_pin_and_discovery_are_read_only(monkeypatch):
    monkeypatch.setenv('POLYA_JACOBIAN_MCP','/path/that/is/not/here')
    p=pin()
    assert p['version']=='0.23.0' and len(p['release_source_sha'])==40
    assert not inspect_runtime()['executable_found']
    r=run('jacobian.find',{'query':'determinant of matrix'})['result']
    assert r['status']=='UNAVAILABLE' and r['data'] is None
    assert r['upstream_version']=='0.23.0'
    assert find(operation_id='jacobian.run')['cache_policy']=='never'
    assert {'jacobian.find','jacobian.run'} <= {x['operation_id'] for x in find('jacobian math',limit=20)}


def test_fake_mcp_discovery_inspection_and_exact_composition(fake_backend):
    found=run('jacobian.find',{'query':'exact extended gcd','limit':3})
    assert found['result']['status']=='OK'
    assert found['result']['data']['matches'][0]['operation_id']=='integer.compute.extended_gcd'
    assert found['receipt']['independently_reproduced'] is False
    inspected=run('jacobian.find',{'operation_id':'integer.compute.extended_gcd'})['result']
    assert inspected['status']=='OK' and inspected['data']['kind']=='operation'
    answer=run('jacobian.run',{'operation_id':'integer.compute.extended_gcd',
                               'payload':{'left':'84','right':'30'}})['result']
    assert answer['status']=='OK' and answer['data']['output']['gcd']=='6'
    assert answer['upstream_tool']=='math.run'
    assert inspect_runtime()['executable_found']


def test_version_mismatch_rejected_before_math_execution(fake_backend, monkeypatch):
    monkeypatch.setenv('FAKE_JACOBIAN_MODE','version')
    outcome=run_math('integer.compute.extended_gcd',{'left':'84','right':'30'})
    assert outcome['status']=='VERSION_MISMATCH' and outcome['data'] is None


def test_wrong_server_identity_is_not_accepted(fake_backend, monkeypatch):
    monkeypatch.setenv('FAKE_JACOBIAN_MODE','impostor')
    outcome=find_math(query='matrix rank')
    assert outcome['status']=='PROTOCOL_ERROR'


def test_upstream_error_not_recast_as_mathematical_unsat(fake_backend, monkeypatch):
    monkeypatch.setenv('FAKE_JACOBIAN_MODE','upstream_error')
    outcome=run_math('integer.compute.extended_gcd',{'left':'84','right':'30'})
    assert outcome['status']=='UPSTREAM_ERROR'
    assert outcome['error']['code']=='INVALID_REQUEST'
    assert outcome['data'] is None


def test_broken_projected_output_not_accepted(fake_backend, monkeypatch):
    monkeypatch.setenv('FAKE_JACOBIAN_MODE','bad_output')
    assert find_math(query='matrix rank')['status']=='PROTOCOL_ERROR'
    assert run_math('integer.compute.extended_gcd',{})['status']=='PROTOCOL_ERROR'


def test_oversize_host_output_is_not_truncated_into_a_result(fake_backend, monkeypatch):
    monkeypatch.setenv('FAKE_JACOBIAN_MODE','oversize')
    out=find_math(query='gcd')
    assert out['status']=='PROTOCOL_ERROR' and out['data'] is None


def test_kill_hung_upstream(fake_backend, monkeypatch):
    monkeypatch.setenv('FAKE_JACOBIAN_MODE','hang')
    begin=time.monotonic()
    result=find_math(query='gcd',timeout_ms=1000)
    assert result['status']=='TIMEOUT' and result['data'] is None
    assert time.monotonic()-begin<4


@pytest.mark.parametrize('inputs', [
    {'query':'   '}, {'query':'a','operation_id':'integer.compute.extended_gcd'},
    {'operation_id':'invalid'}, {'operation_id':'integer.compute.extended_gcd','namespace':'integer'},
    {'query':'x','limit':False}, {'query':'x','timeout_ms':False},
    {'operation_id':'integer.compute.extended_gcd','search_mode':'broad'},
])
def test_invalid_search_parameters_do_not_start_jacobian(fake_backend, inputs):
    with pytest.raises(ValueError):
        run('jacobian.find',inputs)


def test_non_json_and_oversized_payloads_are_rejected_without_leaking_secrets(fake_backend):
    with pytest.raises((ValueError,TypeError)):
        run('jacobian.run',{'operation_id':'integer.compute.extended_gcd',
                            'payload':{'not_json':float('nan')}})
    outcome=run_math('integer.compute.extended_gcd',{'long':'x'*550000})
    assert outcome['status']=='PROTOCOL_ERROR'
