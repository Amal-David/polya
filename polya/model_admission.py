"""Bounded model diagnostics and explicit, exact integer-linear normalization.

Inspection never solves a model, invents a variable domain or silently changes a
solver request. A caller must submit the returned model explicitly for execution.
"""
from __future__ import annotations

from copy import deepcopy
from functools import reduce
import hashlib
import math
from typing import Literal

from pydantic import Field, JsonValue, ValidationError

from .automata import StrictModel
from .model import LIMIT, PuzzleModel, op


RAW_INTEGER_BITS = 256
NORMALIZATION_INTEGER_BITS = 1024
MAX_DIAGNOSTICS = 64
# An expression edge includes both an AST object and its JSON args list.
# Leave room for all 32 admitted edges plus the model/rule and DFA envelopes;
# _guard_expressions still enforces the unchanged 32-level AST contract.
RAW_CONTAINER_DEPTH = 80


class InspectInput(StrictModel):
    model: dict[str, JsonValue]
    assumptions: list[str] = Field(default_factory=list, max_length=1024)
    normalize_coefficients: bool = False


class ModelDiagnostic(StrictModel):
    path: list[str | int]
    code: str
    message: str
    recovery: str


class ModelRewrite(StrictModel):
    path: list[str | int]
    before_sha256: str
    after_sha256: str
    rule: Literal['exact_integer_linear_reduction'] = 'exact_integer_linear_reduction'


class FailedCheck(StrictModel):
    phase: Literal['setup', 'satisfiability', 'enumeration', 'uniqueness', 'forced_value']
    variable: str | None = None
    status: Literal['UNAVAILABLE', 'UNSUPPORTED']
    reason: str


CAPABILITIES = {
    'integer_arithmetic': 'Bounded integer variables; affine add/sub/neg and multiplication by one integer literal.',
    'nonlinear_multiplication': False,
    'nonlinear_recovery': 'A variable-by-variable product is unsupported. Reformulate only with a justified equivalent finite model; no bounds are inferred.',
    'bitvectors': 'Explicit unsigned widths 1..64; bit-vector expressions are never integer-normalized.',
    'normalization': 'Opt-in integer-affine comparisons only; exact gcd, cancellation and integer floor/ceiling. No rational or floating-point coercion.',
    'normalization_limits': f'Input JSON <=1 MB, raw integers <2^{RAW_INTEGER_BITS}, intermediate integers <2^{NORMALIZATION_INTEGER_BITS}; existing AST/domain/output limits remain.',
    'backend_scope': 'Structural admission only. CP-SAT additionally excludes bit-vectors/nested automata and enforces overflow bounds at execution; inspect backends.inspect for runtime availability.',
}

DOMAIN_EXAMPLES = {
    'bounded_integer': {'lower': 0, 'upper': 3},
    'explicit_integer_domain': {'values': [-2, 0, 2]},
    'boolean': {'kind': 'bool'},
    'unsigned_bitvector': {'kind': 'bitvec', 'width': 4},
    'scope': 'Examples only. Choose justified domains from source evidence; these values are never inserted into a model.',
}


class _NormalizationLimit(ValueError):
    def __init__(self, message, path):
        super().__init__(message)
        self.path = path


def _canonical(value):
    # Reuse the receipt encoding after catalog construction, avoiding import cycles.
    from .catalog import canonical_json
    return canonical_json(value)


def _hash(value):
    return hashlib.sha256(_canonical(value).encode('utf8')).hexdigest()


def _path(path):
    return [part if type(part) is int or len(str(part)) <= 128 else str(part)[:125] + '...'
            for part in path[:64]]


def _diagnostic(path, code, message, recovery):
    return {'path': _path(path), 'code': code, 'message': str(message)[:1000],
            'recovery': recovery}


def _validation_diagnostic(error):
    message = error['msg']
    if 'inclusive bounds or values' in message:
        code = 'bounded_domain_required'
        recovery = 'Provide explicit distinct values OR both inclusive lower/upper bounds for this variable. Do not infer bounds from the example.'
    elif 'multiplication by an integer literal' in message:
        code = 'nonlinear_multiplication_unsupported'
        recovery = 'Use literal-times-integer-expression multiplication. Variable-by-variable multiplication is outside this AST; no automatic nonlinear reformulation is performed.'
    elif 'integer literal exceeds' in message:
        code = 'integer_literal_limit'
        recovery = f'Each executed integer literal must be within +/-{LIMIT}. Inspect with normalize_coefficients=true only for exact integer-linear reduction; irreducible oversized constants remain invalid.'
    elif 'integer domain exceeds' in message:
        code = 'integer_domain_limit'
        recovery = f'Keep supplied integer domain values/bounds within +/-{LIMIT}. Normalization does not alter domains.'
    else:
        code = error['type']
        recovery = 'Correct this field against the inspected schema. No domain, coercion or hypothesis is supplied automatically.'
    return _diagnostic(('model', *error['loc']), code, message, recovery)


def _guard_raw(model):
    """Bound memory/arithmetic before copying or normalizing an unvalidated model."""
    stack = [(model, ('model',), 0)]
    seen = 0
    while stack:
        value, path, depth = stack.pop()
        seen += 1
        if depth > RAW_CONTAINER_DEPTH or seen > 100_000:
            raise _NormalizationLimit('raw model nesting/node budget exceeded', path)
        if type(value) is int and value.bit_length() > RAW_INTEGER_BITS:
            raise _NormalizationLimit('raw integer exceeds inspection normalization limit', path)
        if type(value) is dict:
            stack.extend((child, (*path, key), depth + 1) for key, child in value.items())
        elif type(value) is list:
            stack.extend((child, (*path, index), depth + 1) for index, child in enumerate(value))


def _guard_expressions(model):
    constraints = model.get('constraints', [])
    if type(constraints) is not list or len(constraints) > 1024:
        return  # The typed schema reports the shape/length diagnostic.
    stack = [(rule['expr'], ('model', 'constraints', index, 'expr'), 0)
             for index, rule in enumerate(constraints) if type(rule) is dict and 'expr' in rule]
    nodes = 0
    while stack:
        expression, path, depth = stack.pop()
        nodes += 1
        if depth > 32 or nodes > 20_000:
            raise _NormalizationLimit('expression nesting/node budget exceeded', path)
        if type(expression) is dict and set(expression) == {'op', 'args'} and type(expression['args']) is list:
            if len(expression['args']) > 512:
                raise _NormalizationLimit('expression argument budget exceeded', path)
            stack.extend((child, (*path, 'args', index), depth + 1)
                         for index, child in enumerate(expression['args']))


def _bounded_integer(value, path):
    if value.bit_length() > NORMALIZATION_INTEGER_BITS:
        raise _NormalizationLimit('integer-linear normalization intermediate limit exceeded', path)
    return value


def _affine(expression, integer_variables, path):
    """Return integer coefficients/constant only for the declared linear grammar."""
    if type(expression) is int:
        return {}, expression
    if type(expression) is str:
        return ({expression: 1}, 0) if expression in integer_variables else None
    if (type(expression) is not dict or set(expression) != {'op', 'args'}
            or type(expression['args']) is not list or not 1 <= len(expression['args']) <= 512):
        return None
    name, arguments = expression['op'], expression['args']
    if name not in ('add', 'sub', 'neg', 'mul'):
        return None
    if name in ('sub', 'mul') and len(arguments) != 2 or name == 'neg' and len(arguments) != 1:
        return None
    if name == 'mul' and not any(type(argument) is int for argument in arguments):
        return None
    parts = [_affine(argument, integer_variables, (*path, 'args', index))
             for index, argument in enumerate(arguments)]
    if any(part is None for part in parts):
        return None
    if name == 'mul':
        literal_index = 0 if type(arguments[0]) is int else 1
        scalar = arguments[literal_index]
        coefficients, constant = parts[1 - literal_index]
        return ({variable: _bounded_integer(coefficient * scalar, path)
                 for variable, coefficient in coefficients.items() if coefficient * scalar},
                _bounded_integer(constant * scalar, path))
    coefficients = {}
    constant = 0
    for index, (terms, offset) in enumerate(parts):
        sign = -1 if name == 'neg' or name == 'sub' and index == 1 else 1
        constant = _bounded_integer(constant + sign * offset, path)
        for variable, coefficient in terms.items():
            coefficients[variable] = _bounded_integer(coefficients.get(variable, 0) + sign * coefficient, path)
    return {variable: coefficient for variable, coefficient in coefficients.items() if coefficient}, constant


def _comparison(name, left, right, path):
    coefficients, constant = dict(left[0]), left[1] - right[1]
    _bounded_integer(constant, path)
    for variable, coefficient in right[0].items():
        coefficients[variable] = _bounded_integer(coefficients.get(variable, 0) - coefficient, path)
    coefficients = {variable: coefficient for variable, coefficient in coefficients.items() if coefficient}
    bound = -constant
    divisor = reduce(math.gcd, (abs(coefficient) for coefficient in coefficients.values()), 0)
    if not divisor:
        return {'eq': 0 == bound, 'ne': 0 != bound, 'lt': 0 < bound,
                'le': 0 <= bound, 'gt': 0 > bound, 'ge': 0 >= bound}[name]
    if name in ('eq', 'ne'):
        if bound % divisor:
            return name == 'ne'
        bound //= divisor
    elif name in ('le', 'lt'):
        bound = (bound - (name == 'lt')) // divisor
        name = 'le'
    else:
        bound = -((-bound) // divisor) if name == 'ge' else bound // divisor + 1
        name = 'ge'
    coefficients = {variable: coefficient // divisor for variable, coefficient in sorted(coefficients.items())}
    if next(iter(coefficients.values())) < 0:
        coefficients = {variable: -coefficient for variable, coefficient in coefficients.items()}
        bound = -bound
        name = {'le': 'ge', 'ge': 'le'}.get(name, name)
    terms = [variable if coefficient == 1 else op('mul', coefficient, variable)
             for variable, coefficient in coefficients.items()]
    return op(name, terms[0] if len(terms) == 1 else op('add', *terms), bound)


def _normalize_expression(expression, integer_variables, path, rewrites):
    if type(expression) is not dict or set(expression) != {'op', 'args'} or type(expression['args']) is not list:
        return expression
    arguments = [_normalize_expression(argument, integer_variables, (*path, 'args', index), rewrites)
                 for index, argument in enumerate(expression['args'])]
    candidate = {'op': expression['op'], 'args': arguments}
    if expression['op'] in ('eq', 'ne', 'lt', 'le', 'gt', 'ge') and len(arguments) == 2:
        left, right = [_affine(argument, integer_variables, (*path, 'args', index))
                       for index, argument in enumerate(arguments)]
        if left is not None and right is not None:
            candidate = _comparison(expression['op'], left, right, path)
            if _canonical(candidate) != _canonical(expression):
                rewrites.append({'path': list(path), 'before_sha256': _hash(expression),
                                 'after_sha256': _hash(candidate), 'rule': 'exact_integer_linear_reduction'})
    return candidate


def inspect_model(model, assumptions=None, normalize_coefficients=False):
    """Inspect a raw model and return a separately executable admitted representation."""
    if type(model) is not dict or type(normalize_coefficients) is not bool:
        raise ValueError('model must be an object and normalize_coefficients a boolean')
    assumptions = [] if assumptions is None else assumptions
    if type(assumptions) is not list or len(assumptions) > 1024 or any(type(item) is not str for item in assumptions):
        raise ValueError('assumptions must be a list of at most 1024 strings')
    source_json = _canonical(model)
    if len(source_json) > 1_000_000:
        raise ValueError('input JSON exceeds 1 MB prototype admission limit')
    source_hash = hashlib.sha256(source_json.encode('utf8')).hexdigest()
    diagnostics, rewrites, normalized, model_hash = [], [], None, None
    try:
        _guard_raw(model)
        _guard_expressions(model)
        candidate = deepcopy(model)
        if normalize_coefficients:
            variables = candidate.get('variables', {})
            integer_variables = {name for name, variable in variables.items()
                                 if type(variable) is dict and variable.get('kind', 'int') == 'int'} if type(variables) is dict else set()
            constraints = candidate.get('constraints', [])
            if type(constraints) is list and len(constraints) <= 1024:
                for index, rule in enumerate(constraints):
                    if type(rule) is dict and 'expr' in rule:
                        rule['expr'] = _normalize_expression(rule['expr'], integer_variables,
                                                            ('model', 'constraints', index, 'expr'), rewrites)
        admitted = PuzzleModel.model_validate(candidate)
        try:
            admitted.active(assumptions)
        except ValueError as exc:
            diagnostics.append(_diagnostic(('assumptions',), 'invalid_assumptions', exc,
                                           'Name distinct IDs of declared hypothesis rules; observations/derived rules are always active.'))
        if not diagnostics:
            normalized = admitted.model_dump(mode='json')
            model_hash = _hash(normalized)
    except _NormalizationLimit as exc:
        diagnostics.append(_diagnostic(exc.path, 'inspection_resource_limit', exc,
                                       'Reduce the raw model. Inspection never raises execution admission limits.'))
    except ValidationError as exc:
        diagnostics.extend(_validation_diagnostic(error) for error in exc.errors(include_input=False, include_url=False))
    return {'status': 'INVALID' if diagnostics else 'VALID', 'valid': not diagnostics,
            'diagnostics': diagnostics[:MAX_DIAGNOSTICS], 'diagnostics_truncated': len(diagnostics) > MAX_DIAGNOSTICS,
            'normalized_model': normalized, 'input_model_sha256': source_hash,
            'normalized_model_sha256': model_hash, 'normalization_applied': bool(rewrites),
            'rewrites': rewrites, 'capabilities': deepcopy(CAPABILITIES), 'domain_examples': deepcopy(DOMAIN_EXAMPLES),
            'scope': 'Structural admission of the supplied model only; no solving, inferred bounds, source authentication or validation of clue interpretation. Submit the returned model explicitly for execution.'}
