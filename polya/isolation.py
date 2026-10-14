"""Bounded supervision of trusted local operations. This is not a security sandbox."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

from .jsonio import loads

CLAIM = 'No puzzle hypothesis was rejected by this execution outcome.'


@dataclass(frozen=True)
class Limits:
    wall_ms: int = 30000
    memory_mb: int | None = None
    cpu_seconds: int | None = None
    output_bytes: int = 2200000

    def __post_init__(self):
        for name, low, high in [('wall_ms',1,120000), ('memory_mb',128,8192),
                                ('cpu_seconds',1,120), ('output_bytes',1024,2200000)]:
            value = getattr(self,name)
            if value is None and name in ('memory_mb','cpu_seconds'):
                continue
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f'{name} must be in [{low}, {high}]')


class ExecutionError(RuntimeError):
    def __init__(self, report):
        self.execution_report = report
        super().__init__(f"{report['execution_status']}: {report['reason']}. {CLAIM}")


def _kill(process):
    if process.poll() is not None:
        return
    try:
        if os.name == 'posix':
            os.killpg(process.pid, signal.SIGKILL)
            return
    except ProcessLookupError:
        # The child may have exited while the supervisor was deciding to kill.
        return
    except PermissionError:
        # macOS hardened runners can deny killpg even when killing the direct
        # child is permitted. Fall back to the child PID and still reap it.
        pass
    try:
        process.kill()
    except ProcessLookupError:
        pass


def run_isolated(operation_id: str, inputs: dict, *, limits: Limits | None = None,
                 cancel: threading.Event | None = None) -> dict:
    """Run only a registered operation in a disposable worker; never a supplied script.

    Deadlines include startup after Popen returns; OS process creation itself may
    not be interruptible. CPU/address-space limits are opt-in and fail closed.
    """
    limits = limits or Limits()
    if not isinstance(limits, Limits):
        raise TypeError('limits must be Limits')
    if type(operation_id) is not str or type(inputs) is not dict:
        raise ValueError('operation_id must be text and inputs an object')
    from .catalog import canonical_json, canonical_operation_id, REGISTRY, unknown_operation
    operation_id = canonical_operation_id(operation_id)
    if operation_id not in REGISTRY:
        raise unknown_operation(operation_id)
    raw = canonical_json(inputs)
    if len(raw.encode()) > 1000000:
        raise ValueError('input exceeds 1 MB')
    payload = canonical_json({'operation_id':operation_id,'inputs':inputs,'limits':asdict(limits)}).encode()
    started = time.monotonic()
    process = None

    def report(status, reason=None, envelope=None, applied=None):
        return {'execution_status':status,'reason':reason,'envelope':envelope,
                'worker_pid':process.pid if process else None,
                'worker_reaped':process is not None and process.returncode is not None,
                'elapsed_ms':round((time.monotonic()-started)*1000,3),
                'limits':asdict(limits),'applied_limits':applied,
                'claim':CLAIM if status != 'COMPLETED' else 'Only the enclosed operation scope is established.',
                'security_sandbox':False}

    if cancel is not None and cancel.is_set():
        return report('CANCELLED','cancelled before spawn')
    try:
        process = subprocess.Popen([sys.executable,str(Path(__file__).with_name('_worker.py'))],
                                   stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                   start_new_session=os.name=='posix',close_fds=True)
    except OSError as exc:
        return report('UNAVAILABLE',str(exc))
    overflow = threading.Event()
    stdout, stderr = bytearray(), bytearray()

    def collect(stream, buffer, bound):
        try:
            while True:
                part = stream.read(32768)
                if not part: break
                remaining = bound-len(buffer)
                buffer.extend(part[:max(0,remaining)])
                if len(part)>remaining:
                    overflow.set()
                    break
        finally:
            stream.close()

    def send():
        try:
            process.stdin.write(payload)
            process.stdin.flush()
        except (BrokenPipeError,OSError):
            pass
        finally:
            process.stdin.close()

    threads = [threading.Thread(target=collect,args=(process.stdout,stdout,limits.output_bytes),daemon=True),
               threading.Thread(target=collect,args=(process.stderr,stderr,65536),daemon=True),
               threading.Thread(target=send,daemon=True)]
    for thread in threads: thread.start()
    status, reason = None, None
    try:
        while process.poll() is None:
            if cancel is not None and cancel.is_set():
                status,reason='CANCELLED','caller cancellation'; break
            if overflow.is_set():
                status,reason='OUTPUT_LIMIT','worker output limit'; break
            if (time.monotonic()-started)*1000 >= limits.wall_ms:
                status,reason='TIMED_OUT','wall-clock deadline'; break
            time.sleep(0.005)
    finally:
        if process.poll() is None:
            _kill(process)
        process.wait()
        for thread in threads: thread.join(timeout=2)
    if status:
        return report(status,reason)
    if overflow.is_set():
        return report('OUTPUT_LIMIT','worker output limit')
    if any(t.is_alive() for t in threads):
        _kill(process)
        return report('ERROR','worker pipes did not close')
    if process.returncode != 0:
        return report('ERROR',f'worker exited with code {process.returncode}; resource termination or runtime failure')
    try:
        response = loads(bytes(stdout))
        if type(response) is not dict or type(response.get('ok')) is not bool:
            raise ValueError('invalid worker envelope')
        if not response['ok']:
            state = response.get('execution_status','ERROR')
            return report(state if state in ('ERROR','UNAVAILABLE') else 'ERROR',
                          response.get('error','worker failed'),applied=response.get('applied_limits'))
        envelope = response['envelope']
        if type(envelope) is not dict or set(envelope) != {'operation_id','result','receipt'} or envelope['operation_id'] != operation_id:
            raise ValueError('invalid operation envelope')
        return report('COMPLETED',envelope=envelope,applied=response['applied_limits'])
    except (ValueError,KeyError,TypeError) as exc:
        return report('ERROR',f'invalid worker response: {exc}')
