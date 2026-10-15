import json
from pathlib import Path
import pytest
from scripts.jacobian_requirement import requirement

PIN = Path(__file__).resolve().parents[1] / 'polya' / 'jacobian_pin.json'


def test_requirement_uses_reviewed_runtime_not_observed_latest():
    pin = json.loads(PIN.read_text())
    expected = f'jacobian=={pin["version"]} --hash=sha256:{pin["wheel_sha256"]}\n'
    pin.update(latest_available_version='99.0.0', latest_available_wheel_sha256='a' * 64)
    assert requirement(pin) == expected


@pytest.mark.parametrize('field,value', [('version', '0.23.0\nmalware'), ('version', 'main'),
                                        ('wheel_sha256', None), ('wheel_sha256', 'x' * 64),
                                        ('upstream', 'other/repository')])
def test_malformed_pins_fail_closed(field, value):
    pin = json.loads(PIN.read_text()); pin[field] = value
    with pytest.raises(ValueError):
        requirement(pin)
