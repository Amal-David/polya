import subprocess
import sys
import threading
from unittest.mock import patch
import pytest
from polya.isolation import Limits,run_isolated


def fixture_process(code):
    original=subprocess.Popen
    def launch(*args,**kwargs):
        return original([sys.executable,'-c',code],**kwargs)
    return patch('puzzleops.isolation.subprocess.Popen',side_effect=launch)


def test_real_worker_matches_operation_and_is_reaped():
    r=run_isolated('text.profile',{'text':'Aa '})
    assert r['execution_status']=='COMPLETED' and r['worker_reaped']
    assert r['envelope']['result']['codepoint_length']==3
    assert not r['envelope']['receipt']['independently_reproduced']
    assert not r['security_sandbox']


def test_real_error_has_no_puzzle_result():
    r=run_isolated('bytes.decode',{'encoding':'hex','value':'not-hex'})
    assert r['execution_status']=='ERROR' and r['envelope'] is None and r['worker_reaped']


def test_kill_hung_worker_on_wall_deadline():
    with fixture_process('while True: pass'):
        r=run_isolated('text.profile',{'text':'a'},limits=Limits(wall_ms=100))
    assert r['execution_status']=='TIMED_OUT' and r['worker_reaped'] and r['envelope'] is None


def test_cancellation_and_precancellation():
    event=threading.Event(); event.set()
    assert run_isolated('text.profile',{'text':'a'},cancel=event)['worker_pid'] is None
    event.clear(); timer=threading.Timer(0.15,event.set);timer.start()
    try:
        with fixture_process('while True: pass'):
            r=run_isolated('text.profile',{'text':'a'},cancel=event)
        assert r['execution_status']=='CANCELLED' and r['worker_reaped']
    finally: timer.cancel()


@pytest.mark.parametrize('code',["import sys;sys.stdout.write('x'*100000)","import sys;sys.stderr.write('x'*100000)"])
def test_output_flood_is_bounded(code):
    with fixture_process(code):
        r=run_isolated('text.profile',{'text':'a'},limits=Limits(output_bytes=1024))
    assert r['execution_status']=='OUTPUT_LIMIT' and r['worker_reaped']


@pytest.mark.parametrize('code',["print('bad json')","raise RuntimeError('boom')","print('{}')"])
def test_worker_crash_and_bad_response(code):
    with fixture_process(code): r=run_isolated('text.profile',{'text':'a'})
    assert r['execution_status']=='ERROR' and r['envelope'] is None and r['worker_reaped']


@pytest.mark.skipif(sys.platform!='linux',reason='Linux address-space limit')
def test_real_worker_applies_memory_and_cpu_limits():
    r=run_isolated('text.profile',{'text':'a'},limits=Limits(memory_mb=2048,cpu_seconds=5))
    assert r['execution_status']=='COMPLETED',r
    assert r['applied_limits']=={'address_space':True,'cpu':True}


def test_bad_limits_and_unregistered_scripts_rejected():
    for kw in ({'wall_ms':True},{'memory_mb':1},{'cpu_seconds':0}):
        with pytest.raises(ValueError): Limits(**kw)
    with pytest.raises(ValueError): run_isolated('shell',{'command':'echo nope'})


@pytest.mark.skipif(sys.platform=="win32", reason="POSIX process-group fallback")
def test_process_group_permission_denial_falls_back_to_child_kill():
    from unittest.mock import Mock
    from polya.isolation import _kill
    process=Mock(pid=12345)
    process.poll.return_value=None
    with patch('puzzleops.isolation.os.killpg', side_effect=PermissionError('restricted')):
        _kill(process)
    process.kill.assert_called_once_with()
