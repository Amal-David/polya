"""Regression for PR #1: immutable options must precede context creation.

The strict fake proves ordering, not legacy binary compatibility. Separate tests
below execute the real installed Z3 library; record its actual version in CI.
"""
from __future__ import annotations
from unittest import mock
import pytest
from polya import native_z3
from polya.model import PuzzleModel, op
from polya.symbolic import Budget, analyze, solve

class StrictConfigAPI:
    def __init__(self, *, null_config=False, null_context=False, bad_program=False):
        self.events=[]; self.options={}; self.null_config=null_config
        self.null_context=null_context; self.bad_program=bad_program
    def Z3_get_full_version(self): return b'configuration-order-test-double'
    def Z3_mk_config(self):
        self.events.append('config'); return 0 if self.null_config else 1
    def Z3_set_param_value(self, cfg, key, value):
        assert 'context' not in self.events
        self.options[key]=value; self.events.append(('option', key, value))
    def Z3_mk_context(self, cfg):
        assert self.options.get(b'unsat_core') == b'true', 'unsat_core must be configured before context'
        assert self.options.get(b'model') == b'true'
        self.events.append('context'); return 0 if self.null_context else 2
    def Z3_del_config(self, cfg): self.events.append('delete_config')
    def Z3_set_error_handler(self, ctx, handler): self.events.append('handler')
    def Z3_eval_smtlib2_string(self, ctx, data):
        # Reasserting the already enabled option initializes the SMT-LIB
        # command context; changing an immutable native option would be wrong.
        if b':produce-unsat-cores true' in data:
            assert self.options.get(b'unsat_core') == b'true'
        if b':produce-models true' in data:
            assert self.options.get(b'model') == b'true'
        self.events.append('program')
        return b'(error "synthetic malformed program")' if self.bad_program else b''
    def Z3_del_context(self, ctx): self.events.append('delete_context')

def make_engine(api):
    model=PuzzleModel.model_validate({'variables': {}})
    with mock.patch.object(native_z3, 'load_library', return_value=api):
        return native_z3.Z3Engine(model, [], Budget(1000, 10, 10))

def test_options_are_configured_before_context_and_parser_initialization():
    api=StrictConfigAPI(); engine=make_engine(api)
    engine.close(); engine.close()
    assert api.events.index(('option', b'unsat_core', b'true')) < api.events.index('context')
    assert api.events.count('delete_config') == 1
    assert api.events.count('delete_context') == 1

def test_failed_context_frees_config_and_reports_unavailable():
    api=StrictConfigAPI(null_context=True)
    with pytest.raises(native_z3.BackendUnavailable, match='context'): make_engine(api)
    assert api.events.count('delete_config') == 1
    assert 'handler' not in api.events

def test_failed_config_reports_unavailable_without_using_null():
    api=StrictConfigAPI(null_config=True)
    with pytest.raises(native_z3.BackendUnavailable, match='configuration'): make_engine(api)
    assert api.events == ['config']

def test_failed_program_closes_created_context():
    api=StrictConfigAPI(bad_program=True)
    with pytest.raises(ValueError, match='synthetic malformed'): make_engine(api)
    assert api.events.count('delete_context') == 1

def test_standalone_export_retains_required_options():
    emitter=native_z3.Emitter(PuzzleModel.model_validate({'variables': {}}))
    assert '(set-option :produce-unsat-cores true)' in emitter.program([])
    assert '(set-option :produce-models true)' in emitter.program([])

@pytest.mark.skipif(native_z3.native_version() is None, reason='Real native Z3 unavailable')
def test_real_native_sat_unique_and_forced_values():
    model={'variables': {'x': {'lower': 0, 'upper': 9}},
           'constraints': [{'id': 'clue', 'expr': op('eq','x',4)}]}
    result=analyze(model, backend='z3')
    assert result['status']=='SAT'
    assert result['uniqueness']=='UNIQUE'
    assert result['forced_values']=={'x':4}

@pytest.mark.skipif(native_z3.native_version() is None, reason='Real native Z3 unavailable')
def test_real_native_unsat_core_matches_independent_reference():
    constraints=[{'id':'a','expr':op('eq','x',1)}, {'id':'b','expr':op('eq','x',2)}]
    model={'variables':{'x':{'lower':0,'upper':3}},'constraints':constraints}
    result=analyze(model,backend='z3')
    assert result['status']=='UNSAT'
    assert set(result['unsat_core'])=={'a','b'}
    assert solve(model,backend='reference')['status']=='UNSAT'

@pytest.mark.skipif(native_z3.native_version() is None, reason='Real native Z3 unavailable')
def test_real_native_contexts_do_not_leak_constraints():
    for value in (1, 2, 1):
        model={'variables':{'x':{'values':[value]}}}
        assert solve(model,backend='z3')['solutions']==[{'x':value}]
