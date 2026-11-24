# Copyright (c) 2026 btcdage / nextbtc2025
from pathlib import Path
import unittest

class DetailCacheContract(unittest.TestCase):
    def test_confirmed_details_are_cached_and_mempool_is_not(self):
        source=(Path(__file__).resolve().parents[1]/"server.py").read_text(encoding="utf-8")
        self.assertIn("('block-detail',block_hash)", source)
        self.assertIn("cache_put(block_key,payload,3600)", source)
        self.assertIn("('tx-detail',txid,blockhash)", source)
        self.assertIn("cache_put(confirmed_cache_key,payload,3600)", source)
        self.assertIn("response.headers['X-Explorer-Cache']='BYPASS'", source)
        self.assertIn("response.headers['Cache-Control']='no-store'", source)

if __name__ == '__main__': unittest.main()
