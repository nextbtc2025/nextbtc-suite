# Copyright (c) 2026 btcdage / nextbtc2025
# Project: nextBTC Index Server
# Source: https://github.com/nextbtc2025/indexserver
# License: MIT (see LICENSE)

import ast
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

class TestExplorerApiContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = (ROOT / 'server.py').read_text(encoding='utf-8')
        tree = ast.parse(source)
        routes = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for dec in node.decorator_list:
                    if (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute)
                            and dec.func.attr in {'get', 'post'} and dec.args
                            and isinstance(dec.args[0], ast.Constant)):
                        routes.add((dec.func.attr.upper(), dec.args[0].value))
        cls.routes = routes
        cls.source = source

    def test_every_explorer_route_is_documented(self):
        version = (ROOT / 'VERSION').read_text(encoding='utf-8').strip()
        docs = (ROOT / f'API_MATRIX_V{version}.md').read_text(encoding='utf-8')
        documented = set(re.findall(r'\| (GET|POST) \| `([^`]+)` \|', docs))
        actual = {(m, p) for m, p in self.routes if p.startswith('/api/v1/explorer/')}
        self.assertEqual(actual, documented, f'undocumented={actual-documented}; stale={documented-actual}')

    def test_capabilities_reports_current_api_version(self):
        version = (ROOT / 'VERSION').read_text(encoding='utf-8').strip()
        self.assertIn(f"explorer_api_version='{version}'", self.source)
        self.assertIn(f"'explorer_api_v{version.replace('.', '_')}':service!='wallet'", self.source)

    def test_release_readme_uses_current_release_version(self):
        version = (ROOT / 'VERSION').read_text(encoding='utf-8').strip()
        readme = (ROOT / f'README_EXPLORER_V{version}.md').read_text(encoding='utf-8')
        self.assertTrue(readme.startswith(f'# nextBTC Index Server V{version} —'))

    def test_runtime_defaults_keep_core_rpc_loopback_and_blank_credentials(self):
        tree = ast.parse(self.source)
        defaults_node = next(node for node in tree.body
                             if isinstance(node, ast.Assign)
                             and any(isinstance(target, ast.Name) and target.id == 'DEFAULTS'
                                     for target in node.targets))
        defaults = ast.literal_eval(defaults_node.value)
        self.assertEqual(defaults['rpc']['url'], 'http://127.0.0.1:8554')
        self.assertEqual(defaults['rpc']['user'], '')
        self.assertEqual(defaults['rpc']['password'], '')
        self.assertEqual(defaults['server']['host'], '127.0.0.1')

    def test_wallet_and_explorer_have_independent_default_ports(self):
        tree = ast.parse(self.source)
        defaults_node = next(node for node in tree.body
                             if isinstance(node, ast.Assign)
                             and any(isinstance(target, ast.Name) and target.id == 'DEFAULTS'
                                     for target in node.targets))
        defaults = ast.literal_eval(defaults_node.value)
        self.assertEqual(defaults['server']['port'], '8777')
        self.assertEqual(defaults['explorer']['port'], '8778')
        self.assertEqual(defaults['server']['host'], '127.0.0.1')
        self.assertEqual(defaults['explorer']['host'], '127.0.0.1')

    def test_launcher_creates_two_isolated_waitress_apps(self):
        self.assertIn("service='wallet'", self.source)
        self.assertIn("service='explorer'", self.source)
        self.assertIn("Wallet API listening", self.source)
        self.assertIn("Explorer listening", self.source)
        self.assertIn("NEXTBTC_SERVICE_ROUTES", self.source)

    def test_service_factory_enforces_pre_dispatch_route_allowlists(self):
        self.assertIn("if service == 'wallet':", self.source)
        self.assertIn("elif service == 'explorer':", self.source)
        self.assertIn("return jsonify(error='Not found'), 404", self.source)
        self.assertIn("request.path.startswith('/api/v1/explorer/')", self.source)
        self.assertIn("service='wallet'", self.source)
        self.assertIn("service='explorer'", self.source)
        self.assertIn("from waitress import create_server", self.source)
        self.assertIn("Wallet API listening", self.source)
        self.assertIn("Explorer listening", self.source)
        self.assertIn("do not mutate Werkzeug's private URL-map internals", self.source)

    def test_build_script_uses_current_release_version(self):
        build = (ROOT / 'build_windows.bat').read_text(encoding='utf-8')
        version = (ROOT / 'VERSION').read_text(encoding='utf-8').strip()
        self.assertIn(f'nextBTC_IndexServer_V{version}', build)

    def test_all_explorer_routes_are_read_only_get(self):
        for method, path in self.routes:
            if path.startswith('/api/v1/explorer/'):
                self.assertEqual(method, 'GET', path)

    def test_critical_visualizer_routes_exist(self):
        expected = {
            ('GET', '/api/v1/explorer/difficulty'),
            ('GET', '/api/v1/explorer/difficulty/history'),
            ('GET', '/api/v1/explorer/difficulty/window'),
            ('GET', '/api/v1/explorer/mempool/map'),
            ('GET', '/api/v1/explorer/mempool/fees'),
            ('GET', '/api/v1/explorer/mempool/dependencies'),
        }
        # Dependencies route is tx-specific; test the exact registered path.
        expected.remove(('GET', '/api/v1/explorer/mempool/dependencies'))
        expected.add(('GET', '/api/v1/explorer/mempool/tx/<txid>/dependencies'))
        self.assertTrue(expected.issubset(self.routes), expected - self.routes)

    def test_windows_build_is_onefile_console_and_bundles_explorer_assets(self):
        build=(ROOT/'build_windows.bat').read_text(encoding='utf-8')
        self.assertIn('--onefile',build)
        self.assertIn('--console',build)
        self.assertIn('--add-data "web/explorer;web/explorer"',build)
        server=(ROOT/'server.py').read_text(encoding='utf-8')
        self.assertIn("Path(getattr(sys,'_MEIPASS',BASE))",server)

if __name__ == '__main__':
    unittest.main()
