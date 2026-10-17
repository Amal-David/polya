"""Integration/negative controls for educational method retrieval and preparation."""
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
import subprocess
import sys

import jsonschema
import pytest

from polya import find, run
from polya.catalog import _implementation_source_snapshot
from polya.methods.evaluation import Budget, build_context, check_equal_budget, make_manifests, skill_fingerprint
from polya.methods.library import builtin_library, read_json, read_text
from polya.methods.reset import Archive, canonical
from polya.mcp_server import Server

ROOT = Path(__file__).resolve().parents[1]


def manifests():
    return make_manifests(model='unit-test-only', seed=0, task_ids=['toy'],
                          skill_hash='a' * 64, library_hash='b' * 64)


def test_registry_retrieval_is_scoped_detached_and_source_linked():
    payload = {'query': 'parity invariant coloring', 'limit': 2}
    result = run('method.retrieve', payload)
    assert result['result']['matches'][0]['example']['id'] == 'color-balance-invariant'
    assert len(result['result']['library_sha256']) == 64
    assert not result['receipt']['independently_reproduced']
    jsonschema.validate(result['result'], find(operation_id='method.retrieve')['output_schema'])
    result['result']['matches'][0]['example']['source']['license_basis'] = 'tampered'
    fresh = run('method.retrieve', payload)['result']
    assert fresh['matches'][0]['example']['source']['license_basis'] != 'tampered'
    assert run('method.retrieve', {'query': 'zzznomatchzzz'})['result']['matches'] == []
    # A solution-only word is not a feature for candidate selection.
    assert run('method.retrieve', {'query': '121'})['result']['matches'] == []


def test_legacy_nested_imports_keep_module_and_class_identity():
    import polya.methods.library as primary
    import puzzleops.methods.library as alias
    import polya.methods.evaluation as scorer
    import puzzleops.methods.evaluation as old_scorer
    assert primary is alias and primary.Example is alias.Example
    assert scorer is old_scorer and scorer.Budget is old_scorer.Budget


@pytest.mark.parametrize('inputs', [
    {'query': ' '}, {'query': 'x' * 4097}, {'query': 'parity', 'limit': 7},
    {'query': 'parity', 'limit': True}, {'query': 'parity', 'path': '/tmp/any'},
])
def test_registry_rejects_malformed_or_unbounded_inputs(inputs):
    with pytest.raises(ValueError):
        run('method.retrieve', inputs)


def test_retrieval_cli_and_mcp_share_the_operation():
    args = {'query': 'parity invariant', 'limit': 1}
    cli = subprocess.run([sys.executable, '-m', 'polya', 'run', 'method.retrieve',
                          '--json', json.dumps(args)], cwd=ROOT, capture_output=True, text=True, timeout=15)
    assert cli.returncode == 0, cli.stderr
    expected = run('method.retrieve', args)['result']
    assert json.loads(cli.stdout)['result'] == expected
    server = Server()
    server.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
                   'params': {'protocolVersion': '2025-06-18'}})
    server.handle({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
    result = server.handle({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call',
        'params': {'name': 'puzzle.run', 'arguments': {'operation_id': 'method.retrieve', 'inputs': args}}})
    assert not result['result']['isError']
    assert result['result']['structuredContent']['data']['result'] == expected


def test_published_schema_agrees_on_whitespace_and_identifier_boundaries():
    schema = read_json(ROOT / 'polya/methods/data/example.schema.json')
    examples = [x.to_dict() for x in builtin_library()]
    jsonschema.validate(examples, schema)
    for key, value in [('id', examples[0]['id'] + '\n'), ('documented_evidence', ' \n\t')]:
        broken = deepcopy(examples)
        broken[0][key] = value
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(broken, schema)


def test_all_offline_input_reads_are_bounded_and_strict(tmp_path):
    path = tmp_path / 'input.json'
    for raw in ['{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}', '{"x":1e400}']:
        path.write_text(raw)
        with pytest.raises(ValueError):
            read_json(path)
    path.write_bytes(b' ' * 2_000_001)
    with pytest.raises(ValueError):
        read_text(path)
    result = subprocess.run([sys.executable, '-m', 'polya.methods', 'context', str(path),
                             '--arm', 'baseline'], capture_output=True, text=True, timeout=15)
    assert result.returncode != 0 and 'byte limit' in result.stderr


@pytest.mark.parametrize('mutation', ['extra', 'missing', 'version_bool', 'budget_bool', 'status', 'arm', 'tasks'])
def test_every_manifest_is_strictly_validated(mutation):
    values = manifests()
    m = values[-1]
    if mutation == 'extra': m['unexpected'] = 1
    elif mutation == 'missing': del m['library_hash']
    elif mutation == 'version_bool': m['schema_version'] = True
    elif mutation == 'budget_bool': m['budget']['resets'] = True
    elif mutation == 'status': m['status'] = 'completed'
    elif mutation == 'arm': m['arm'] = 'baseline'
    else: m['task_ids'] = [{}]
    with pytest.raises(ValueError):
        check_equal_budget(values)


def test_manifests_do_not_claim_experiments_and_skill_must_exist(tmp_path):
    values = manifests()
    assert all(m['status'] == 'planned_not_run' for m in values)
    values[0]['task_ids'].append('other')
    assert values[1]['task_ids'] == ['toy']
    with pytest.raises(ValueError):
        skill_fingerprint(tmp_path / 'missing.md')
    skill = tmp_path / 'SKILL.md'; skill.write_text('skill')
    refs = tmp_path / 'references'; refs.mkdir()
    binary = refs / 'diagram.bin'; binary.write_bytes(b'\x00\xff')
    before = skill_fingerprint(skill)
    binary.write_bytes(b'\x00\xfe')
    assert before != skill_fingerprint(skill)


def test_json_identity_rejects_python_coercions_and_excess_depth():
    for value in [{1: 'ambiguous'}, ('tuple',), float('nan')]:
        with pytest.raises(ValueError):
            canonical(value)
    value = []
    for _ in range(66): value = [value]
    with pytest.raises(ValueError, match='depth'):
        canonical(value)
    with pytest.raises(ValueError, match='node'):
        canonical([None] * 100_001)
    assert canonical(3) != canonical('3') != canonical(3.0)


def test_fresh_packet_preserves_scope_unknown_and_large_integer_budget(tmp_path):
    archive = Archive(tmp_path)
    evidence = archive.record_verified('Only the tiny declared domain was checked',
        {'status': 'UNKNOWN', 'scope': 'not a global impossibility', 'checked_cases': 3}, 'independent-toy-check')
    packet = archive.fresh_packet('Original toy problem', evidence_ids=[evidence],
                                  remaining_budget={'tool_calls': 10 ** 400})
    assert packet['verified_evidence'][0]['receipt']['status'] == 'UNKNOWN'
    assert packet['remaining_budget']['tool_calls'] == 10 ** 400
    assert 'attempts' not in packet


def test_fingerprints_cover_nested_implementation_and_bundled_data(tmp_path):
    (tmp_path / 'root.py').write_text('root')
    nested = tmp_path / 'methods'; nested.mkdir()
    code = nested / 'library.py'; code.write_text('one')
    data = nested / 'data'; data.mkdir()
    corpus = data / 'examples.json'; corpus.write_text('[]')
    a = _implementation_source_snapshot(tmp_path)
    code.write_text('two')
    b = _implementation_source_snapshot(tmp_path)
    corpus.write_text('[1]')
    c = _implementation_source_snapshot(tmp_path)
    assert len({a, b, c}) == 3


def test_six_development_fixtures_pass_independent_checks():
    result = subprocess.run([sys.executable, str(ROOT / 'scripts/verify_method_examples.py')],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert result.stdout.count('PASS ') == 7
