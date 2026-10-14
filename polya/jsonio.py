"""Strict external JSON: duplicate keys and non-finite numbers are rejected."""
import json

def loads(raw):
    def pairs(items):
        out={}
        for key,value in items:
            if key in out: raise ValueError(f'Duplicate JSON object key: {key!r}')
            out[key]=value
        return out
    def constant(value): raise ValueError(f'Non-finite JSON number: {value}')
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=constant)
