"""Fixed worker entry point; launched by path to set limits before package import."""
import json
from pathlib import Path
import sys


def main():
    applied = {'address_space':False,'cpu':False}
    try:
        raw = sys.stdin.buffer.read(1001001)
        if len(raw)>1001000: raise ValueError('worker input limit')
        request = json.loads(raw)
        limits = request['limits']
        memory, cpu = limits['memory_mb'], limits['cpu_seconds']
        if memory is not None or cpu is not None:
            try:
                import resource
                if memory is not None:
                    if sys.platform != 'linux':
                        raise RuntimeError('address-space limits are supported on Linux only')
                    resource.setrlimit(resource.RLIMIT_AS,(memory*1024*1024,memory*1024*1024))
                    applied['address_space']=True
                if cpu is not None:
                    resource.setrlimit(resource.RLIMIT_CPU,(cpu,cpu))
                    applied['cpu']=True
            except (ImportError,ValueError,OSError,RuntimeError) as exc:
                print(json.dumps({'ok':False,'execution_status':'UNAVAILABLE','error':str(exc),'applied_limits':applied}))
                return 0
        sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
        from polya import run
        envelope = run(request['operation_id'],request['inputs'])
        print(json.dumps({'ok':True,'envelope':envelope,'applied_limits':applied},ensure_ascii=True,allow_nan=False))
    except Exception as exc:
        print(json.dumps({'ok':False,'execution_status':'ERROR','error':f'{type(exc).__name__}: {exc}','applied_limits':applied}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
