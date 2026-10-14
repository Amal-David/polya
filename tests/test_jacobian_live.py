"""Real Jacobian release integration, executed only by the dedicated CI job."""
import os
import math
import pytest
from polya import run
from polya.jacobian_bridge import pin


@pytest.mark.skipif(not os.environ.get('POLYA_JACOBIAN_MCP'), reason='Requires a separately installed reviewed Jacobian release')
def test_real_pinned_release_find_inspect_and_run():
    assert pin()['version']=='0.23.0', 'Update real integration expectation with a reviewed release pin'
    found=run('jacobian.find',{'query':'exact extended gcd of two integers', 'limit':5,'timeout_ms':60000})['result']
    assert found['status']=='OK',found
    matches=found['data']['matches']
    assert matches and any(r['operation_id']=='integer.compute.extended_gcd' for r in matches),found
    inspected=run('jacobian.find',{'operation_id':'integer.compute.extended_gcd','timeout_ms':60000})['result']
    assert inspected['status']=='OK' and inspected['data']['kind']=='operation',inspected
    schema=inspected['data']['operation']['input_schema']
    assert 'left' in schema.get('properties',{}) and 'right' in schema.get('properties',{})
    for left, right in [('84', '30'), ('-84', '30'), ('0', '30'), ('0', '0'),
                        ('9007199254740993', '30')]:
        output=run('jacobian.run',{'operation_id':'integer.compute.extended_gcd',
                                  'payload':{'left':left,'right':right}, 'timeout_ms':60000})['result']
        assert output['status']=='OK',output
        assert output['data']['operation_id']=='integer.compute.extended_gcd'
        exact = output['data']['output']
        assert exact['gcd'] == str(math.gcd(int(left), int(right))), output
        assert int(left) * int(exact['left_coefficient']) + int(right) * int(exact['right_coefficient']) == int(exact['gcd'])
