# Copyright (c) 2026 btcdage / nextbtc2025
# Project: nextBTC Index Server
# Source: https://github.com/nextbtc2025/indexserver
# License: MIT (see LICENSE)

import unittest
from mempool import fee_histogram

class TestFeeHistogram(unittest.TestCase):
    def test_all_transactions_including_high_fee_outliers_are_counted(self):
        txs={
            'a':{'vsize':100,'fee_sats':50},
            'b':{'vsize':100,'fee_sats':2500},
            'c':{'vsize':1,'fee_sats':2_000_000},
            'd':{'vsize':100,'fee_sats':0},
        }
        bins=fee_histogram(txs)
        self.assertEqual(sum(x['count'] for x in bins),len(txs))
        self.assertEqual(bins[-1]['count'],1)
        self.assertEqual(sum(x['vsize'] for x in bins),301)
        self.assertEqual(sum(x['fee_sats'] for x in bins),2_002_550)

if __name__=='__main__': unittest.main()
