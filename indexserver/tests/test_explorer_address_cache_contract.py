# Copyright (c) 2026 btcdage / nextbtc2025
from pathlib import Path
import unittest

class AddressCacheContract(unittest.TestCase):
    def test_address_endpoints_use_tip_scoped_cache_and_report_status(self):
        source=(Path(__file__).resolve().parents[1]/'server.py').read_text(encoding='utf-8')
        for key in ("('address-history'", "('address-utxos'", "('address-statistics'", "('address-balance-history'"):
            self.assertIn(key, source)
        self.assertGreaterEqual(source.count("response.headers['X-Explorer-Cache']='HIT'"), 3)
        self.assertGreaterEqual(source.count("cache_put(cache_key,payload,10)"), 3)
        self.assertIn('cache_put(cache_key,payload,60)', source)
        self.assertIn("str(tip['hash']),address", source)

if __name__ == '__main__': unittest.main()
