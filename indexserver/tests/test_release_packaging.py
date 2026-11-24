# Copyright (c) 2026 btcdage / nextbtc2025
# Project: nextBTC Index Server
# Source: https://github.com/nextbtc2025/indexserver
# License: MIT (see LICENSE)

import pathlib
import unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
from tools.package_source import should_include

class TestReleasePackaging(unittest.TestCase):
    def test_sample_config_does_not_ship_rpc_credentials(self):
        text=(ROOT/'config.example.ini').read_text(encoding='utf-8').lower()
        self.assertRegex(text,r'(?m)^user\s*=\s*$')
        self.assertRegex(text,r'(?m)^password\s*=\s*$')


    def test_runtime_config_is_not_used_as_public_sample(self):
        sample=(ROOT/'config.example.ini').read_text(encoding='utf-8').lower()
        self.assertIn('url = http://127.0.0.1:8554',sample)
        self.assertRegex(sample,r'(?m)^user\s*=\s*$')
        self.assertRegex(sample,r'(?m)^password\s*=\s*$')

    def test_required_final_tools_and_docs_exist(self):
        version = (ROOT/'VERSION').read_text().strip()
        for rel in [f'README_EXPLORER_V{version}.md',f'API_MATRIX_V{version}.md',f'API_REFERENCE_V{version}.md','DWG_CORE_REFERENCE.md',
                    'tools/verify_dwg_core.py','tools/audit_index_db.py','tools/backup_index_db.py',
                    'tools/run_full_acceptance.py','tools/package_source.py','run_acceptance.bat','run_full_acceptance.bat',
                    f'MIGRATION_V{version}.md','tools/smoke_windows_exe.py','tools/verify_live_explorer.py','config.example.ini']:
            self.assertTrue((ROOT/rel).is_file(),rel)

    def test_source_packager_excludes_runtime_configuration_and_databases(self):
        self.assertFalse(should_include(ROOT/'nextBTC_IndexServer_V1.0.20.exe'))
        self.assertFalse(should_include(ROOT/'src'/'src.zip'))
        self.assertFalse(should_include(ROOT/'config.ini'))
        self.assertFalse(should_include(ROOT/'index.db'))
        self.assertFalse(should_include(ROOT/'backups'/'index_acceptance_20261123.db'))
        self.assertTrue(should_include(ROOT/'config.example.ini'))

    def test_source_packager_excludes_arbitrary_sqlite_and_secret_files(self):
        self.assertFalse(should_include(ROOT/'runtime'/'wallet.sqlite3'))
        self.assertFalse(should_include(ROOT/'runtime'/'cache.db-wal'))
        self.assertFalse(should_include(ROOT/'runtime'/'cache.db-shm'))
        self.assertFalse(should_include(ROOT/'runtime'/'.env'))
        self.assertFalse(should_include(ROOT/'runtime'/'config.local.ini'))

    def test_acceptance_requires_a_full_test_collection_and_pyinstaller(self):
        from tools.run_full_acceptance import MIN_EXPECTED_TESTS
        self.assertGreaterEqual(MIN_EXPECTED_TESTS, 81)
        dev = (ROOT / 'requirements-dev.txt').read_text().lower()
        self.assertIn('pyinstaller', dev)
        self.assertIn('-r requirements.txt', dev)

    def test_version_metadata_is_aligned(self):
        version=(ROOT/'VERSION').read_text().strip()
        self.assertRegex(version,r'^\d+\.\d+\.\d+$')
        server=(ROOT/'server.py').read_text(encoding='utf-8')
        build=(ROOT/'build_windows.bat').read_text(encoding='utf-8')
        self.assertIn(f"explorer_api_version='{version}'",server)
        self.assertIn(f'nextBTC_IndexServer_V{version}',build)

if __name__=='__main__': unittest.main()
