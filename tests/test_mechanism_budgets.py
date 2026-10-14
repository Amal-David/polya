"""Budget accounting must include constant payloads and default fields."""
import json
from unittest.mock import patch
import pytest
from polya.mechanisms import scan
from examples.cryptic_demo import step


@pytest.mark.parametrize("operation_id,bound,source,constants,output", [
    ("cipher.polyalphabetic", "key", "B", {"text": "A" * 4096}, "text"),
    ("bytes.decode", "encoding", "hex", {"value": "41" * 2048}, "hex"),
])
def test_budget_counts_large_constants_not_only_bound_input(operation_id,bound,source,constants,output):
    from dataclasses import replace
    from unittest.mock import Mock
    from polya.catalog import REGISTRY
    definition=step(operation_id, constants, input_field=bound, output_field=output,
                    rationale="Adversarial short parameter with large payload")
    args=dict(source=source, stages=[[definition]],
              checkpoint={"kind":"prefix", "value":"Z" if output=="text" else "41", "source":"fixture"})
    original=REGISTRY[operation_id]
    observed=Mock(wraps=original.kernel)
    with patch.dict(REGISTRY,{operation_id:replace(original,kernel=observed)}):
        limited=scan(**args,max_work=100)
        assert limited["termination_reason"]=="work_limit"
        assert limited["next_start"]==0 and not limited["complete"]
        assert limited["kernel_calls"]==0 and limited["work_units"]==0
        observed.assert_not_called()
        admitted=scan(**args,max_work=20000)
    assert admitted["complete"] and len(admitted["matches"])==1
    assert admitted["kernel_calls"]==1
    full=original.request.model_validate(constants|{bound:source}).model_dump(mode="json")
    expected=len(json.dumps(full,sort_keys=True,separators=(",",":"),ensure_ascii=True,allow_nan=False))
    assert admitted["work_units"]==expected
    assert admitted["work_units"]>len(source)+len(next(iter(constants.values())))
