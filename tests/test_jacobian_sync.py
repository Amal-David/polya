"""Pure synchronization logic regression without network or GitHub credentials."""
from __future__ import annotations
import json
from pathlib import Path
import tempfile
import unittest
from scripts.sync_jacobian import snapshot, main

PIN = Path(__file__).resolve().parents[1] / 'polya/jacobian_pin.json'


def payload(version='0.23.0',sha='a'*40):
    gh={'object':{'sha':sha}}
    py={'info':{'name':'jacobian','version':version,'requires_python':'>=3.12,<3.14'},
        'urls':[{'packagetype':'bdist_wheel','filename':f'jacobian-{version}-py3-none-any.whl',
                 'digests':{'sha256':'b'*64}}]}
    return gh, py


class SyncTest(unittest.TestCase):
    def setUp(self):
        self.current=json.loads(PIN.read_text(encoding='utf8'))

    def test_source_change_does_not_mutate_runtime_release(self):
        gh,py=payload('0.24.0')
        updated=snapshot(self.current,gh,py)
        self.assertEqual(updated['version'],self.current['version'])
        self.assertEqual(updated['release_source_sha'],self.current['release_source_sha'])
        self.assertEqual(updated['upstream_main_sha'],'a'*40)
        self.assertEqual(updated['latest_available_version'],'0.24.0')
        self.assertEqual(updated['latest_available_wheel_sha256'],'b'*64)

    def test_reject_bad_source_metadata_and_inexact_wheels(self):
        gh,py=payload()
        with self.assertRaises(ValueError):snapshot(self.current,{'object':{'sha':'bad'}},py)
        py['info']['name']='wrong'
        with self.assertRaises(ValueError):snapshot(self.current,gh,py)
        _,py=payload();py['urls'].append(py['urls'][0]);
        with self.assertRaises(ValueError):snapshot(self.current,gh,py)

    def test_idempotence_and_offline_cli_no_hidden_changes(self):
        gh,py=payload('0.23.0',self.current['upstream_main_sha'])
        py['urls'][0]['digests']['sha256']=self.current['wheel_sha256']
        with tempfile.TemporaryDirectory() as folder:
            d=Path(folder)
            a,b,m=d/'github.json',d/'pypi.json',d/'pin.json'
            a.write_text(json.dumps(gh));b.write_text(json.dumps(py));m.write_text(json.dumps(self.current))
            args=['--github-json',str(a),'--pypi-json',str(b),'--manifest',str(m)]
            self.assertEqual(main(args+['--apply']),0)
            contents=m.read_text()
            self.assertEqual(main(args+['--apply']),0)
            self.assertEqual(m.read_text(),contents)
            self.assertEqual(json.loads(contents)['version'],'0.23.0')
