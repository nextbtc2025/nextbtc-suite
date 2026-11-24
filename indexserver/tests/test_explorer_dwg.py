# Copyright (c) 2026 btcdage / nextbtc2025
# Project: nextBTC Index Server
# Source: https://github.com/nextbtc2025/indexserver
# License: MIT (see LICENSE)

import unittest
from explorer import compact_to_target, target_to_compact, predict_dgw, network_series

POW_LIMIT = int('00000fffffffffffffffffffffffffffffffffffffffffffffffffffffffffff', 16)

class TestDWG(unittest.TestCase):
    def test_main_chain_block_60000_matches_confirmed_target_and_core_hashps(self):
        # getblockheader for heights 59,999..59,976 in descending order. The
        # expected outputs came from getblockheader and getnetworkhashps(24,60000).
        inputs = [
            (1754781989,'1c048f9a'), (1754781787,'1c055585'), (1754782004,'1c04dd69'),
            (1754781598,'1c050e0d'), (1754781535,'1c055866'), (1754781490,'1c05687c'),
            (1754781462,'1c0671d3'), (1754781452,'1c076f65'), (1754781432,'1c068e8e'),
            (1754781063,'1c06d4bc'), (1754780994,'1c06eb78'), (1754780965,'1c078f92'),
            (1754780741,'1c0a9c01'), (1754780571,'1c0a7992'), (1754780572,'1c0acf22'),
            (1754780542,'1c0a9bce'), (1754780525,'1c0a68de'), (1754780390,'1c09c4fe'),
            (1754780166,'1c0990bf'), (1754780091,'1c097041'), (1754780039,'1c09b9da'),
            (1754779968,'1c099c07'), (1754779905,'1c09db93'), (1754779817,'1c09eb0f')]
        headers=[{'height':59999-i,'time':ts,'bits':bits} for i,(ts,bits) in enumerate(inputs)]
        result=predict_dgw(headers,60000)
        self.assertEqual(result['actual_timespan'],2172)
        self.assertEqual(result['predicted_nbits'],'1c04dac9')
        confirmed={'height':60000,'bits':'1c04dac9','time':1754782017,
                   'hash':'000000000465aeec467a8064104b8531b5fbc7f8adab4ccaa8375e8f2a678d8b'}
        series=network_series([confirmed,*headers],1)[0]
        self.assertEqual(series['hashrate_window_blocks'],24)
        self.assertAlmostEqual(series['hashrate_hps'],1672841588.351364,delta=0.000001)

    def test_hashrate_unknown_without_elapsed_time(self):
        header={'time':42,'bits':'1e0fffff'}
        rows=network_series([header,header],2)
        self.assertEqual([item['hashrate_window_blocks'] for item in rows],[1,0])
        self.assertEqual([item['hashrate_hps'] for item in rows],[None,None])

    def test_compact_round_trip_core_pow_limit(self):
        bits = target_to_compact(POW_LIMIT)
        self.assertEqual(bits, 0x1e0fffff)
        self.assertEqual(compact_to_target(f'{bits:08x}'), compact_to_target(bits))
        self.assertLessEqual(compact_to_target(bits), POW_LIMIT)

    def test_instant_mine_phase_boundary(self):
        result = predict_dgw([], 55554)
        self.assertEqual(result['phase'], 'instant_mine')
        self.assertEqual(result['predicted_nbits'], '1e0fffff')
        self.assertFalse(predict_dgw([], 55555)['available'])

    def test_dgw_full_window_uses_24_target_intervals_and_core_timespan(self):
        # Newest first. 24 blocks have 23 measured timestamp intervals,
        # while Core target timespan is CountBlocks * 150 = 3600 seconds.
        headers = [{'bits':'1e0fffff','time':1_700_000_000-i*150,'height':55554-i} for i in range(24)]
        result = predict_dgw(headers, 55555)
        self.assertTrue(result['available'])
        self.assertEqual(result['window_blocks'], 24)
        self.assertEqual(result['timestamp_intervals'], 23)
        self.assertEqual(result['target_timespan'], 3600)
        self.assertEqual(result['actual_timespan'], 3450)
        self.assertNotEqual(result['predicted_nbits'], '1e0fffff')  # 23 measured intervals vs 24*150 target

    def test_exact_core_activation_boundary_at_candidate_55555(self):
        # Core checks candidate height < 55555 for instant mine. Candidate 55555
        # enters DGW using previous block height 55554.
        instant = predict_dgw([], 55554)
        self.assertEqual(instant['phase'], 'instant_mine')
        headers = [{'bits':'1e0fffff','time':1_700_000_000-i*150,'height':55554-i} for i in range(24)]
        active = predict_dgw(headers, 55555)
        self.assertEqual(active['phase'], 'dgw_v3')
        self.assertTrue(active['available'])

    def test_dgw_timespan_lower_and_upper_clamps(self):
        fast = [{'bits':'1e0fffff','time':1_700_000_000-i,'height':55554-i} for i in range(24)]
        slow = [{'bits':'1e0fffff','time':1_700_000_000-i*1000,'height':55554-i} for i in range(24)]
        a = predict_dgw(fast, 55555)
        b = predict_dgw(slow, 55555)
        self.assertTrue(a['clamped']); self.assertEqual(a['clamped_timespan'], 1200)
        self.assertTrue(b['clamped']); self.assertEqual(b['clamped_timespan'], 10800)

if __name__ == '__main__': unittest.main()
