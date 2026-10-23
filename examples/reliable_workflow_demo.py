"""Synthetic source-bound continuation; no model, service or network is called."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from polya.workflows import Continuation


def example() -> tuple[dict, dict, dict[str, str]]:
    text = '01000001'
    case = {'id': 'synthetic-byte-conventions', 'question': 'Check the explicitly declared equality pattern',
            'artifacts': [{'id': 'evidence', 'encoding': 'utf8', 'content': text,
                           'sha256': hashlib.sha256(text.encode()).hexdigest(), 'source': 'synthetic bit string'}]}
    plan = {'sources': [{'id': 'source', 'kind': 'bits', 'value': text, 'source': 'synthetic bit string'}],
            'nodes': [{'id': 'packed', 'alternatives': [
                {'operation_id': 'bits.pack', 'bindings': {'text': {'node': 'source', 'field': 'value'}},
                 'inputs': {'bit_order': order, 'tail': 'reject'}, 'rationale': 'two explicit bit-order conventions'}
                for order in ('msb', 'lsb')]}],
            'candidate': {'node': 'packed', 'field': 'hex'},
            'target': {'kind': 'equality_pattern', 'target': {'pattern': 'AB',
                       'source': 'two-position equality requirement', 'digest': 'none', 'representation': 'bytes'}}}
    return case, plan, {'source': 'evidence'}


def run_demo(directory: str | Path) -> dict:
    with Continuation(directory) as flow:
        case, plan, bindings = example()
        handle = flow.workspace.put(b'01000001')
        case['artifacts'][0]['content'] = None
        plan['sources'][0].pop('value')
        plan['sources'][0]['artifact_ref'] = handle
        ticket = flow.prepare(case, plan, bindings)
        first = flow.run_page(ticket['ticket_ref'], max_trials=1)
        assert not flow.handoff(ticket['ticket_ref'])['local_coverage']['complete']
    with Continuation(directory) as flow:
        second = flow.run_page(ticket['ticket_ref'], max_trials=1)
        result = flow.handoff(ticket['ticket_ref'])
        assert first['result']['stop'] == second['result']['start'] == 1
        assert result['local_coverage']['complete']
        assert result['counts']['unique_completed_ordinals'] == 2
        assert result['independent_replay'] == 'NOT_ESTABLISHED'
        return result


if __name__ == '__main__':
    with TemporaryDirectory() as directory:
        print(json.dumps(run_demo(directory), indent=2, allow_nan=False))
