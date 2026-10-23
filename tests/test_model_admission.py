"""Exact integer reductions are checked against a separate tiny interpreter."""
from copy import deepcopy
import hashlib
import itertools
import json
import random

import pytest

from polya.model import LIMIT, PuzzleModel, op
from polya.model_admission import RAW_CONTAINER_DEPTH, inspect_model


def model(expression, variables=None):
    return {'variables': variables or {'x': {'lower': -3, 'upper': 3}, 'y': {'lower': -3, 'upper': 3}},
            'constraints': [{'id': 'synthetic', 'expr': expression}]}


def independent(expression, assignment):
    if type(expression) in (bool, int):
        return expression
    if type(expression) is str:
        return assignment[expression]
    name = expression['op']
    arguments = [independent(child, assignment) for child in expression['args']]
    if name == 'add':
        return sum(arguments)
    if name == 'sub':
        return arguments[0] - arguments[1]
    if name == 'neg':
        return -arguments[0]
    if name == 'mul':
        return arguments[0] * arguments[1]
    if name == 'and':
        return all(arguments)
    if name == 'or':
        return any(arguments)
    if name == 'not':
        return not arguments[0]
    left, right = arguments
    return {'eq': left == right, 'ne': left != right, 'lt': left < right,
            'le': left <= right, 'gt': left > right, 'ge': left >= right}[name]


def truth_set(expression):
    return {(x, y) for x, y in itertools.product(range(-3, 4), repeat=2)
            if independent(expression, {'x': x, 'y': y})}


@pytest.mark.parametrize('comparison', ['eq', 'ne', 'lt', 'le', 'gt', 'ge'])
@pytest.mark.parametrize('coefficient,bound', [(4, 3), (4, -3), (-4, 3), (-4, -3),
                                             (0, 0), (0, -1), (0, 1)])
def test_integer_rounding_zero_and_negative_signs(comparison, coefficient, bound):
    expression = op(comparison, op('mul', coefficient, 'x'), bound)
    result = inspect_model(model(expression), normalize_coefficients=True)
    assert result['valid'], result
    reduced = result['normalized_model']['constraints'][0]['expr']
    assert truth_set(expression) == truth_set(reduced)


@pytest.mark.parametrize('seed', range(72))
def test_large_common_factors_and_cancellation_match_small_domain_exhaustion(seed):
    rng = random.Random(seed)
    factor = (10**13 + 7) * rng.choice([-3, -2, 1, 2, 5])
    a, b, c = [rng.randrange(-5, 6) for _ in range(3)]
    # The repeated x term cancels, independently of signs or whether the bound
    # is divisible by the remaining coefficient gcd.
    expression = op(rng.choice(['eq', 'ne', 'lt', 'le', 'gt', 'ge']),
                    op('add', op('mul', factor * a, 'x'), op('mul', factor * b, 'y'),
                       op('sub', op('mul', 3 * factor, 'x'), op('mul', 3 * factor, 'x'))),
                    factor * c + rng.randrange(-2, 3))
    request = model(expression)
    original = deepcopy(request)
    result = inspect_model(request, normalize_coefficients=True)
    assert result['valid'], result
    assert request == original
    reduced = result['normalized_model']['constraints'][0]['expr']
    assert truth_set(expression) == truth_set(reduced)
    assert result['normalization_applied']
    assert result['rewrites']
    assert all(len(rewrite['before_sha256']) == len(rewrite['after_sha256']) == 64
               for rewrite in result['rewrites'])


def test_reduction_is_explicit_and_ordinary_admission_remains_unchanged():
    expression = op('ge', op('mul', 4 * LIMIT, 'x'), 6 * LIMIT + 1)
    request = model(expression)
    rejected = inspect_model(request)
    assert not rejected['valid'] and rejected['normalized_model'] is None
    assert rejected['diagnostics'][0]['code'] == 'integer_literal_limit'
    result = inspect_model(request, normalize_coefficients=True)
    assert result['valid']
    assert result['normalized_model']['constraints'][0]['expr'] == op('ge', 'x', 2)
    with pytest.raises(ValueError, match='integer literal exceeds'):
        PuzzleModel.model_validate(request)
    normalized = result['normalized_model']
    encoded = json.dumps(normalized, ensure_ascii=True, sort_keys=True, separators=(',', ':'), allow_nan=False)
    assert result['normalized_model_sha256'] == hashlib.sha256(encoded.encode()).hexdigest()


def test_nondivisible_equalities_and_all_zero_coefficients_are_exact_constants():
    cases = [(op('eq', op('mul', 4, 'x'), 3), False),
             (op('ne', op('mul', 4, 'x'), 3), True),
             (op('eq', op('sub', 'x', 'x'), 0), True),
             (op('lt', op('sub', 'x', 'x'), 0), False),
             (op('ge', op('add', op('mul', 0, 'x'), 2), 2), True)]
    for expression, expected in cases:
        result = inspect_model(model(expression), normalize_coefficients=True)
        assert result['valid']
        assert result['normalized_model']['constraints'][0]['expr'] is expected


@pytest.mark.parametrize('comparison', ['eq', 'ne', 'lt', 'le', 'gt', 'ge'])
def test_both_sides_offsets_literal_order_and_boolean_composition(comparison):
    factor = 10**13 + 9
    left = op('add', op('neg', op('mul', factor, 'x')),
              op('mul', 'y', 2 * factor), factor)
    right = op('sub', op('mul', factor, 'y'), -2 * factor + 1)
    predicate = op(comparison, left, right)
    expression = op('or', op('and', predicate, op('ne', 'x', 'y')),
                    op('not', op('lt', op('mul', -2, 'x'), 1)))
    result = inspect_model(model(expression), normalize_coefficients=True)
    assert result['valid'], result
    reduced = result['normalized_model']['constraints'][0]['expr']
    assert truth_set(expression) == truth_set(reduced)


def test_field_diagnostics_and_examples_do_not_invent_domains():
    missing = inspect_model({'variables': {'n': {}}})
    assert not missing['valid'] and missing['normalized_model'] is None
    assert missing['diagnostics'][0]['path'] == ['model', 'variables', 'n']
    assert missing['diagnostics'][0]['code'] == 'bounded_domain_required'
    assert missing['domain_examples']['bounded_integer'] == {'lower': 0, 'upper': 3}
    assert 'never inserted' in missing['domain_examples']['scope']
    nonlinear = inspect_model(model(op('eq', op('mul', 'x', 'y'), 1)), normalize_coefficients=True)
    assert not nonlinear['valid']
    assert nonlinear['diagnostics'][0]['path'] == ['model', 'constraints', 0, 'expr']
    assert nonlinear['diagnostics'][0]['code'] == 'nonlinear_multiplication_unsupported'
    assert nonlinear['capabilities']['nonlinear_multiplication'] is False


@pytest.mark.parametrize('expression', [op('eq', 'x', True), op('eq', 'x', 1.0),
                                       op('eq', op('mul', True, 'x'), 0),
                                       op('eq', op('mul', 2.0, 'x'), 0),
                                       op('eq', op('sub', 'absent', 'absent'), 0),
                                       op('eq', op('mul', 0, op('mul', 'x', 'y')), 0)])
def test_normalization_does_not_erase_invalid_types_names_or_nonlinearity(expression):
    result = inspect_model(model(expression), normalize_coefficients=True)
    assert not result['valid'] and result['normalized_model'] is None


def test_domain_and_irreducible_literal_limits_remain_in_force():
    result = inspect_model(model(op('le', 'x', 2), {'x': {'lower': 0, 'upper': LIMIT + 1}}),
                           normalize_coefficients=True)
    assert not result['valid'] and result['diagnostics'][0]['code'] == 'integer_domain_limit'
    result = inspect_model(model(op('le', op('add', op('mul', LIMIT + 1, 'x'), 'y'), 0)),
                           normalize_coefficients=True)
    assert not result['valid'] and result['diagnostics'][0]['code'] == 'integer_literal_limit'


def test_unsigned_bitvector_semantics_are_never_integer_reduced():
    request = model(op('eq', {'bv': 1, 'width': 4}, 'x'), {'x': {'kind': 'bitvec', 'width': 4}})
    result = inspect_model(request, normalize_coefficients=True)
    assert result['valid'] and not result['normalization_applied']
    assert result['normalized_model']['constraints'][0]['expr'] == request['constraints'][0]['expr']


@pytest.mark.parametrize('depth', [30, 31, 32, 33])
@pytest.mark.parametrize('normalize_coefficients', [False, True])
def test_inspection_and_execution_agree_at_expression_depth_boundary(depth, normalize_coefficients):
    expression = True
    for _ in range(depth):
        expression = op('not', expression)
    request = model(expression)
    if depth <= 32:
        PuzzleModel.model_validate(request)
    else:
        with pytest.raises(ValueError, match='expression nesting/node budget exceeded'):
            PuzzleModel.model_validate(request)
    result = inspect_model(request, normalize_coefficients=normalize_coefficients)
    assert result['valid'] is (depth <= 32)
    if depth <= 32:
        assert result['normalized_model']['constraints'][0]['expr'] == expression
    else:
        assert result['normalized_model'] is None
        assert result['diagnostics'][0]['code'] == 'inspection_resource_limit'
        assert result['diagnostics'][0]['message'] == 'expression nesting/node budget exceeded'


@pytest.mark.parametrize('normalize_coefficients', [False, True])
def test_raw_guard_allows_dfa_envelope_beneath_maximum_expression_depth(normalize_coefficients):
    from polya.automata import from_runs

    expression = {'op': 'automaton', 'vars': [], 'machine': from_runs([])['machine']}
    for _ in range(32):
        expression = op('not', expression)
    request = model(expression)
    PuzzleModel.model_validate(request)
    result = inspect_model(request, normalize_coefficients=normalize_coefficients)
    assert result['valid'] and result['normalized_model']['constraints'][0]['expr'] == expression


def test_raw_container_guard_still_bounds_non_expression_data():
    nested = {}
    for _ in range(RAW_CONTAINER_DEPTH + 1):
        nested = {'child': nested}
    result = inspect_model({'variables': {}, 'unexpected': nested})
    assert not result['valid'] and result['normalized_model'] is None
    assert result['diagnostics'][0]['code'] == 'inspection_resource_limit'
    assert result['diagnostics'][0]['message'] == 'raw model nesting/node budget exceeded'


def test_raw_intermediate_ast_and_json_budgets_reject_before_reduction():
    expression = op('eq', op('mul', 2**256, 'x'), 0)
    assert inspect_model(model(expression), normalize_coefficients=True)['diagnostics'][0]['code'] == 'inspection_resource_limit'
    expression = 'x'
    for _ in range(6):
        expression = op('mul', 2**200, expression)
    result = inspect_model(model(op('eq', expression, 0)), normalize_coefficients=True)
    assert not result['valid'] and 'intermediate' in result['diagnostics'][0]['message']
    expression = 'x'
    for _ in range(33):
        expression = op('neg', expression)
    result = inspect_model(model(op('eq', expression, 0)), normalize_coefficients=True)
    assert not result['valid'] and 'budget exceeded' in result['diagnostics'][0]['message']
    request = {'variables': {'x': {'values': [0]}}, 'constraints': [
        {'id': str(index), 'expr': op('eq', op('add', *(['x'] * 50)), 0)} for index in range(400)]}
    result = inspect_model(request, normalize_coefficients=True)
    assert not result['valid'] and result['diagnostics'][0]['code'] == 'inspection_resource_limit'
    assert not result['normalization_applied']
    request = model(True)
    request['constraints'][0]['note'] = 'x' * 1_000_001
    with pytest.raises(ValueError, match='1 MB'):
        inspect_model(request)


def test_errors_are_bounded_and_assumptions_checked_without_enabling_them():
    request = {'variables': {}, 'constraints': [{'id': str(index), 'expr': 'missing'} for index in range(100)]}
    result = inspect_model(request)
    assert not result['valid'] and len(result['diagnostics']) == 64 and result['diagnostics_truncated']
    request = model(True)
    request['constraints'][0]['kind'] = 'hypothesis'
    result = inspect_model(request, assumptions=['missing'])
    assert not result['valid'] and result['diagnostics'][0]['path'] == ['assumptions']
    assert inspect_model(request, assumptions=[])['valid']
