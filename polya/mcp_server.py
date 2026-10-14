"""Small synchronous stdio MCP transport (protocol 2025-06-18).

Dependency-free, two discover/run tools, no HTTP listener, no shell or URL tools.
Supports initialization, notifications/initialized, ping, tools/list, tools/call.
Cancellation/progress/subscriptions are not advertised or implemented.
"""
from __future__ import annotations
import json
import sys
from . import __version__,find,run
from .jsonio import loads

MAX_LINE=1_000_000
VERSIONS=('2025-06-18','2025-03-26','2024-11-05')
TOOLS=[
    {'name':'puzzle.find','description':'Find operations, or inspect the exact contract for one operation before running it.',
     'inputSchema':{'type':'object','properties':{'query':{'type':'string'},'operation_id':{'type':'string'},
                    'limit':{'type':'integer','minimum':1,'maximum':100}},'additionalProperties':False},
     'annotations':{'readOnlyHint':True,'destructiveHint':False,'openWorldHint':False}},
    {'name':'puzzle.run','description':'Run one bounded operation. Inspect its contract with puzzle.find first. '
                 'Results establish only their explicit scope; UNKNOWN and partial results never mean UNSAT.',
     'inputSchema':{'type':'object','properties':{'operation_id':{'type':'string'},'inputs':{'type':'object'}},
                    'required':['operation_id','inputs'],'additionalProperties':False},
     'annotations':{'readOnlyHint':True,'destructiveHint':False,'openWorldHint':False}},
]


def error(request_id,code,message):
    return {'jsonrpc':'2.0','id':request_id,'error':{'code':code,'message':message}}


class Server:
    def __init__(self): self.initialized=False; self.ready=False; self.version=VERSIONS[0]
    def handle(self,message):
        if not isinstance(message,dict) or message.get('jsonrpc')!='2.0' or type(message.get('method')) is not str:
            return error(None,-32600,'Invalid JSON-RPC request')
        notification='id' not in message
        rid=message.get('id')
        if not notification and type(rid) not in (int,str): return error(None,-32600,'Request id must be integer or string')
        method=message['method']; params=message.get('params',{})
        if notification:
            if method=='notifications/initialized' and self.initialized: self.ready=True
            return None
        if not isinstance(params,dict): return error(rid,-32602,'params must be an object')
        if method=='ping': return {'jsonrpc':'2.0','id':rid,'result':{}}
        if method=='initialize':
            if self.initialized: return error(rid,-32600,'Already initialized')
            if type(params.get('protocolVersion')) is not str: return error(rid,-32602,'protocolVersion is required')
            self.version=params['protocolVersion'] if params['protocolVersion'] in VERSIONS else VERSIONS[0]
            self.initialized=True
            return {'jsonrpc':'2.0','id':rid,'result':{'protocolVersion':self.version,
                'capabilities':{'tools':{'listChanged':False}},'serverInfo':{'name':'polya','version':__version__},
                'instructions':'Use puzzle.find to inspect one contract, then puzzle.run. Keep observations and hypotheses '
                 'separate. Verification concerns supplied models; learned conformance is finite, not global.'}}
        if not self.ready: return error(rid,-32002,'Initialize and send notifications/initialized first')
        if method=='tools/list':
            if params.get('cursor') is not None: return error(rid,-32602,'No pagination cursor is valid for this fixed tool list')
            return {'jsonrpc':'2.0','id':rid,'result':{'tools':TOOLS}}
        if method!='tools/call': return error(rid,-32601,'Method not found')
        name=params.get('name'); args=params.get('arguments',{})
        if name not in ('puzzle.find','puzzle.run'): return error(rid,-32602,'Unknown tool')
        if not isinstance(args,dict): return error(rid,-32602,'arguments must be an object')
        try:
            if name=='puzzle.find':
                if set(args)-{'query','operation_id','limit'}: raise ValueError('Unexpected puzzle.find arguments')
                data=find(**args)
            else:
                if set(args)!={'operation_id','inputs'}: raise ValueError('puzzle.run requires exactly operation_id and inputs')
                data=run(args['operation_id'],args['inputs'])
            payload={'data':data}
            text=json.dumps(payload,ensure_ascii=True,allow_nan=False)
            result={'content':[{'type':'text','text':text}],'isError':False}
            if self.version=='2025-06-18': result['structuredContent']=payload
        except Exception as exc:
            # Tool failures are execution errors, never evidence against a puzzle.
            result={'content':[{'type':'text','text':json.dumps({'error_type':type(exc).__name__,
                     'message':str(exc),'claim':'No puzzle hypothesis was rejected by this execution error.'})}],
                    'isError':True}
        return {'jsonrpc':'2.0','id':rid,'result':result}


def main():
    server=Server(); source=sys.stdin.buffer
    while True:
        raw=source.readline(MAX_LINE+1)
        if not raw: return 0
        if len(raw)>MAX_LINE:
            while raw and not raw.endswith(b'\n'): raw=source.readline(MAX_LINE+1)
            response=error(None,-32600,'Input exceeds 1 MB transport limit')
        else:
            try:
                message=loads(raw)
                response=server.handle(message)
            except (ValueError,UnicodeDecodeError,RecursionError):
                response=error(None,-32700,'Invalid JSON')
        if response is not None:
            encoded=json.dumps(response,ensure_ascii=True,allow_nan=False,separators=(',',':'))
            if len(encoded)>2_200_000:
                encoded=json.dumps(error(response.get('id'),-32603,'Output exceeds transport limit; reduce the operation scope'))
            sys.stdout.write(encoded+'\n'); sys.stdout.flush()


if __name__=='__main__': raise SystemExit(main())
