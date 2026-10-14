"""Contract and adversarial transport tests with a deterministic Jacobian-shaped MCP host.

The mock is not claimed as upstream integration. Actual upstream is a separate job.
"""
from __future__ import annotations

import os
import json
from pathlib import Path
import signal
import stat
import subprocess
import sys
import textwrap
import time
from unittest.mock import patch

import pytest

from polya import find, run
from polya.jacobian_bridge import find_math, inspect_runtime, pin, run_math

MOCK = '''#!{python}
import json, os, subprocess, sys, time
mode=os.environ.get('FAKE_JACOBIAN_MODE','ok')
cancel_child=None
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
    elif req.get('method')=='notifications/cancelled':
        if cancel_child is not None:
            if mode=='early_cancel_ack':
                print(json.dumps({{'jsonrpc':'2.0','id':2,'error':{{'code':-32800,'message':'cancelled'}}}}), flush=True)
                time.sleep(0.1)
            cancel_child.kill(); cancel_child.wait()
            with open(os.environ['FAKE_JACOBIAN_CANCELLED'], 'w') as marker: marker.write('reaped')
            print(json.dumps({{'jsonrpc':'2.0','id':2,'error':{{'code':-32800,'message':'cancelled'}}}}), flush=True)
        continue
    elif req.get('method')=='tools/call':
        tool=req['params']['name'];args=req['params']['arguments']
        if mode in ('cooperative_cancel', 'early_cancel_ack'):
            cancel_child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'], start_new_session=os.name=='posix')
            with open(os.environ['FAKE_JACOBIAN_CHILD'], 'w') as marker: marker.write(str(cancel_child.pid))
            continue
        if mode.startswith('tree_'):
            child_code = ('import os, pathlib, signal, sys, time; '
                          'signal.signal(signal.SIGTERM, signal.SIG_IGN); '
                          'pathlib.Path(sys.argv[1]).write_text(str(os.getpid())); '
                          'time.sleep(60)')
            marker=os.environ['FAKE_JACOBIAN_CHILD']
            subprocess.Popen([sys.executable, '-c', child_code, marker])
            ready=time.monotonic()+5
            while (not os.path.exists(marker) or not os.path.getsize(marker)) and time.monotonic()<ready: time.sleep(0.01)
            if mode=='tree_hang': time.sleep(60)
            if mode=='tree_exit': os._exit(0)
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
            if mode=='wrong_operation': data['operation_id']='integer.compute.lcm'
            result={{'jsonrpc':'2.0','id':2,'result':{{'content':[{{'type':'text',
                 'text':json.dumps(data)}}],'structuredContent':data, 'isError':False}}}}
        if mode=='bad_output': result['result']['structuredContent']={{'unexpected':True}}
    else:
        continue
    if mode=='oversize' and req.get('id')==2:
        sys.stdout.write('x'*1100001+'\\n');sys.stdout.flush();continue
    if mode=='notify_forever' and req.get('id')==2:
        while True:
            print(json.dumps({{'jsonrpc':'2.0','method':'notifications/progress','params':{{'data':'x'*2000}}}}), flush=True)
    sys.stdout.write(json.dumps(result,separators=(',',':'))+'\\n');sys.stdout.flush()
    if mode=='notify_after' and req.get('id')==2:
        for _ in range(100):
            print(json.dumps({{'jsonrpc':'2.0','method':'notifications/progress','params':{{'data':'x'*2000}}}}), flush=True)
        time.sleep(60)
    if mode=='stop_reading' and req.get('id')==1: time.sleep(60)
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
            f'"{sys.executable}" "{script}"\n'
            'exit /b 0\n', encoding='utf-8')
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


def test_result_must_belong_to_requested_math_operation(fake_backend, monkeypatch):
    monkeypatch.setenv('FAKE_JACOBIAN_MODE', 'wrong_operation')
    outcome = run_math('integer.compute.extended_gcd', {'left': '84', 'right': '30'})
    assert outcome['status'] == 'PROTOCOL_ERROR' and outcome['data'] is None


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


def test_deadline_covers_large_request_to_initialized_nonreader(fake_backend, monkeypatch):
    import threading
    monkeypatch.setenv('FAKE_JACOBIAN_MODE', 'stop_reading')
    begin = time.monotonic()
    result = run_math('integer.compute.extended_gcd', {'large': 'x' * 400000}, timeout_ms=1000)
    assert result['status'] == 'TIMEOUT' and result['data'] is None
    assert time.monotonic() - begin < 5
    assert not any(t.name == 'polya-jacobian-writer' and t.is_alive() for t in threading.enumerate())


def test_request_writer_completes_partial_writes():
    from types import SimpleNamespace
    from puzzleops.jacobian_bridge import _send
    received = bytearray()

    class ShortWrites:
        def write(self, part):
            received.extend(part[:3])
            return min(3, len(part))

        def flush(self):
            pass

    writers = []
    _send(SimpleNamespace(stdin=ShortWrites()), {'jsonrpc': '2.0', 'id': 7}, time.monotonic() + 1, writers)
    assert json.loads(received) == {'jsonrpc': '2.0', 'id': 7}
    assert received.endswith(b'\n')
    for writer in writers:
        writer.join(timeout=1)


def test_cleanup_kills_before_closing_a_possibly_blocked_input():
    from unittest.mock import Mock
    from puzzleops import jacobian_bridge
    events = []
    process = Mock(pid=12345)
    process.poll.return_value = None
    process.kill.side_effect = lambda: events.append('kill')
    process.stdin.close.side_effect = lambda: events.append('close_input')
    with patch.object(jacobian_bridge.os, 'name', 'nt'):
        jacobian_bridge._stop(process)
    assert events.index('kill') < events.index('close_input')


@pytest.mark.parametrize('failure', [0, BrokenPipeError('closed')])
def test_request_writer_rejects_stalled_or_closed_pipe(failure):
    from types import SimpleNamespace
    from unittest.mock import Mock
    from puzzleops.jacobian_bridge import _send, _BridgeFailure
    stream = Mock()
    if isinstance(failure, Exception):
        stream.write.side_effect = failure
    else:
        stream.write.return_value = failure
    writers = []
    with pytest.raises(_BridgeFailure) as error:
        _send(SimpleNamespace(stdin=stream), {'id': 1}, time.monotonic() + 1, writers)
    assert error.value.status == 'UPSTREAM_ERROR'
    for writer in writers:
        writer.join(timeout=1)


@pytest.mark.parametrize('mode, expected', [('notify_after', 'OK'), ('notify_forever', 'TIMEOUT')])
def test_no_reader_survives_notifications_after_result_or_deadline(fake_backend, monkeypatch, mode, expected):
    import threading
    monkeypatch.setenv('FAKE_JACOBIAN_MODE', mode)
    for _ in range(2):
        result = find_math(query='gcd', timeout_ms=1000)
        assert result['status'] == expected
        assert not any(t.name == 'polya-jacobian-reader' and t.is_alive() for t in threading.enumerate())


@pytest.mark.parametrize('mode', ['cooperative_cancel', 'early_cancel_ack'])
def test_cooperative_cancel_reaps_detached_worker_within_total_budget(fake_backend, monkeypatch, tmp_path, mode):
    marker = tmp_path / 'detached.pid'
    cancelled = tmp_path / 'cancelled'
    monkeypatch.setenv('FAKE_JACOBIAN_MODE', mode)
    monkeypatch.setenv('FAKE_JACOBIAN_CHILD', str(marker))
    monkeypatch.setenv('FAKE_JACOBIAN_CANCELLED', str(cancelled))
    begin = time.monotonic()
    try:
        outcome = find_math(query='gcd', timeout_ms=3000)
        assert outcome['status'] == 'TIMEOUT' and outcome['data'] is None
        assert time.monotonic() - begin < 5
        assert cancelled.read_text() == 'reaped'
        assert not _process_running(int(marker.read_text()))
    finally:
        if marker.exists():
            pid = int(marker.read_text())
            if _process_running(pid):
                if os.name == 'nt':
                    subprocess.run(['taskkill', '/PID', str(pid), '/T', '/F'], check=False,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    os.kill(pid, signal.SIGKILL)


def test_reader_can_cancel_while_notification_queue_is_full():
    import io
    import queue
    import threading
    from puzzleops.jacobian_bridge import _read_messages
    line = json.dumps({'jsonrpc': '2.0', 'method': 'notifications/progress'}).encode() + b'\n'
    inbox = queue.Queue(maxsize=32)
    stopped = threading.Event()
    reader = threading.Thread(target=_read_messages, args=(io.BytesIO(line * 100), inbox, stopped))
    reader.start()
    try:
        deadline = time.monotonic() + 2
        while not inbox.full() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert inbox.full(), 'Exercise the blocked publisher, not just EOF'
        stopped.set()
        reader.join(timeout=1)
        assert not reader.is_alive()
    finally:
        stopped.set()
        reader.join(timeout=1)


def _process_running(pid):
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.WaitForSingleObject.restype = wintypes.DWORD
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.restype = wintypes.BOOL
        handle = kernel.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE
        if not handle:
            assert ctypes.get_last_error() == 87  # ERROR_INVALID_PARAMETER: no such PID
            return False
        try:
            return kernel.WaitForSingleObject(handle, 0) == 258  # WAIT_TIMEOUT
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    if sys.platform == 'linux':
        try:
            # An orphaned zombie is dead; this container's PID 1 may reap late.
            return Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[0] != 'Z'
        except (FileNotFoundError, ProcessLookupError):
            # Linux may remove the task between opening /proc/PID/stat and
            # reading it. ENOENT and ESRCH both mean this process is gone.
            return False
    return True


@pytest.mark.skipif(sys.platform != 'linux', reason='Linux procfs process-removal race')
@pytest.mark.parametrize('error', [FileNotFoundError(), ProcessLookupError()])
def test_process_probe_handles_task_removed_during_read(error):
    with patch('os.kill'), patch.object(Path, 'read_text', side_effect=error):
        assert not _process_running(12345)


@pytest.mark.parametrize('mode, status', [('tree_hang', 'TIMEOUT'), ('tree_ok', 'OK'),
                                          ('tree_exit', 'TIMEOUT')])
def test_cleanup_terminates_descendants_even_after_leader_exits(fake_backend, monkeypatch, tmp_path, mode, status):
    marker = tmp_path / 'child.pid'
    monkeypatch.setenv('FAKE_JACOBIAN_MODE', mode)
    monkeypatch.setenv('FAKE_JACOBIAN_CHILD', str(marker))
    try:
        # Several real process launches are needed on Windows. Allow startup
        # separately from the assertion that no descendant survives cleanup.
        result = find_math(query='gcd', timeout_ms=3000)
        # A Windows job closes when the supervisor exits, so tree_exit can
        # report closed protocol output before the deadline instead of timeout.
        if os.name == 'nt' and mode == 'tree_exit':
            assert result['status'] == 'PROTOCOL_ERROR'
        else:
            assert result['status'] == status
        assert marker.exists(), 'The grandchild must actually start before cleanup'
        pid = int(marker.read_text())
        deadline = time.monotonic() + 3
        while _process_running(pid) and time.monotonic() < deadline:
            time.sleep(0.02)
        assert not _process_running(pid), 'Jacobian grandchild survived bridge cleanup'
    finally:
        if marker.exists():
            pid = int(marker.read_text())
            if _process_running(pid):
                if os.name == 'nt':
                    subprocess.run(['taskkill', '/PID', str(pid), '/T', '/F'], check=False,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    os.kill(pid, signal.SIGKILL)


@pytest.mark.parametrize('field', ['version', 'release_source_sha', 'wheel_sha256',
                                   'upstream', 'requires_python', 'execution'])
def test_runtime_pin_promotions_change_receipt_identity(monkeypatch, field):
    from puzzleops import catalog, jacobian_bridge
    monkeypatch.setenv('POLYA_JACOBIAN_MCP', '/path/that/is/not/here')
    before = run('jacobian.inspect', {})['receipt']
    promoted = pin()
    promoted[field] += '-reviewed-promotion'
    monkeypatch.setattr(jacobian_bridge, '_PIN_SNAPSHOT', json.dumps(promoted))
    monkeypatch.setattr(catalog, '_JACOBIAN_PIN_RUNTIME_SNAPSHOT',
                        catalog.canonical_json(catalog._execution_pin_fields(promoted)).encode('utf8'))
    monkeypatch.setattr(catalog, '_LOADED_FINGERPRINT', None)
    after = run('jacobian.inspect', {})['receipt']
    assert before['implementation_fingerprint'] != after['implementation_fingerprint']
    assert before['experiment_key'] != after['experiment_key']


def test_source_watch_metadata_does_not_promote_runtime_identity(monkeypatch):
    from puzzleops import catalog, jacobian_bridge
    before = run('jacobian.inspect', {})['receipt']
    watched = pin()
    for field in ('upstream_main_sha', 'latest_available_version',
                  'latest_available_wheel_sha256', 'latest_requires_python'):
        watched[field] += '-new-observation'
    monkeypatch.setattr(jacobian_bridge, '_PIN_SNAPSHOT', json.dumps(watched))
    monkeypatch.setattr(catalog, '_JACOBIAN_PIN_RUNTIME_SNAPSHOT',
                        catalog.canonical_json(catalog._execution_pin_fields(watched)).encode('utf8'))
    monkeypatch.setattr(catalog, '_LOADED_FINGERPRINT', None)
    assert run('jacobian.inspect', {})['receipt'] == before


def test_pin_returns_owned_copy_and_does_not_reload_disk(monkeypatch):
    from puzzleops import jacobian_bridge
    original = pin()
    changed = pin()
    changed['version'] = 'unreviewed'
    monkeypatch.setattr(jacobian_bridge, 'files', lambda *_: pytest.fail('Loaded pin must not reopen disk'))
    assert pin() == original


def test_failed_windows_job_setup_never_starts_backend(monkeypatch):
    from puzzleops import _jacobian_worker
    with patch.object(_jacobian_worker.os, 'name', 'nt'), \
            patch.object(_jacobian_worker.sys, 'argv', ['supervisor', 'operator-backend']), \
            patch.object(_jacobian_worker, '_join_job', side_effect=OSError('job setup denied')), \
            patch.object(_jacobian_worker.subprocess, 'Popen') as launch:
        with pytest.raises(OSError, match='job setup denied'):
            _jacobian_worker.main()
        launch.assert_not_called()


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


def test_runtime_pin_revisions_affect_provenance_not_source_observations():
    from polya.jacobian_bridge import pin
    from puzzleops.catalog import _execution_pin_fields, _compute_implementation_fingerprint
    base=pin()
    assert _execution_pin_fields(base)==_execution_pin_fields({**base,"upstream_main_sha":"a"*40})
    assert _execution_pin_fields(base)!=_execution_pin_fields({**base,"version":"999.0"})
    from unittest.mock import patch
    before=_compute_implementation_fingerprint()
    with patch('puzzleops.catalog._JACOBIAN_PIN_RUNTIME_SNAPSHOT', b'different-reviewed-upstream-runtime'):
        after=_compute_implementation_fingerprint()
    assert before!=after


@pytest.mark.skipif(sys.platform=='win32', reason='POSIX process group isolation')
def test_delegated_backend_is_its_own_posix_process_group(fake_backend, monkeypatch):
    import signal
    from unittest.mock import patch
    from polya.jacobian_bridge import _bridge
    seen=[]
    original=os.killpg
    def record(pgid,sig):
        seen.append((pgid,sig))
        return original(pgid,sig)
    with patch('puzzleops.jacobian_bridge.os.killpg', side_effect=record):
        r=find_math(query='extended gcd')
    assert r['status']=='OK'
    assert seen and all(sig==signal.SIGKILL for _,sig in seen)
