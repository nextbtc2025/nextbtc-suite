# Copyright (c) 2026 btcdage / nextbtc2025
# Project: nextBTC Index Server
# Source: https://github.com/nextbtc2025/indexserver
# License: MIT (see LICENSE)

import random
import unittest
from explorer import predict_dgw, verify_template_bits, compact_to_target, target_to_compact, POW_LIMIT_HEX
from tools.verify_dwg_core import POW_LIMITS, GENESIS

class TestDgwTemplate(unittest.TestCase):
    def test_template_requires_bits_and_same_parent(self):
        parent='a'*64
        valid={'height':1,'previousblockhash':parent,'bits':'1e0fffff'}
        prediction=predict_dgw([],1)
        for invalid in (None,{}, {**valid,'bits':None}, {**valid,'bits':'00000000'},
                        {**valid,'bits':'x'}, {**valid,'previousblockhash':'b'*64}):
            with self.subTest(template=invalid):
                check=verify_template_bits(prediction,invalid,1,parent)
                self.assertFalse(check['available'])
                self.assertIsNone(check['matched'])
    def test_template_height_mismatch_is_not_reported_as_consensus_mismatch(self):
        headers=[{'bits':'1e0fffff','time':1700000000-i*150,'height':55554-i} for i in range(24)]
        prediction=predict_dgw(headers,55555)
        result=verify_template_bits(prediction,{'height':55556,'bits':prediction['predicted_nbits']},55555)
        self.assertFalse(result['available'])
        self.assertIsNone(result['matched'])

    def test_exact_template_bits_match_and_mismatch(self):
        headers=[{'bits':'1e0fffff','time':1700000000-i*150,'height':55554-i} for i in range(24)]
        prediction=predict_dgw(headers,55555)
        matched=verify_template_bits(prediction,{'height':55555,'bits':prediction['predicted_nbits']},55555)
        self.assertTrue(matched['matched'])
        mismatch=verify_template_bits(prediction,{'height':55555,'bits':'1e0ffffe'},55555)
        self.assertFalse(mismatch['matched'])

    def test_verifier_supports_core_main_test_and_signet_parameters(self):
        self.assertEqual(set(POW_LIMITS), {'main', 'test', 'signet'})
        self.assertEqual(len({POW_LIMITS[name] for name in POW_LIMITS}), 1)
        self.assertEqual(GENESIS, '000003167643c767d4e015a8bad0fb1054286acf23cfe3009083f9a9cd72dbc1')

    def test_dgw_matches_independent_core_integer_reference_for_varied_windows(self):
        rng = random.Random(20261123)
        pow_limit = int(POW_LIMIT_HEX, 16)

        def core_reference(headers):
            count = 0
            average = 0
            previous_average = 0
            last_time = 0
            actual_timespan = 0
            for header in headers[:24]:
                count += 1
                target = compact_to_target(header['bits'])
                if count <= 24:
                    if count == 1:
                        average = target
                    else:
                        average = (previous_average * (count - 1) + target) // count
                    previous_average = average
                if last_time > 0:
                    actual_timespan += last_time - int(header['time'])
                last_time = int(header['time'])
            target_timespan = count * 150
            actual_timespan = max(target_timespan // 3, min(actual_timespan, target_timespan * 3))
            new_target = (average * actual_timespan) // target_timespan
            new_target = min(new_target, pow_limit)
            return f'{target_to_compact(new_target):08x}'

        for case in range(100):
            newest_time = 1_700_000_000
            headers = []
            for height_offset in range(24):
                # Generate valid compact targets from a broad but bounded range.
                divisor = rng.randint(1, 80)
                target = max(1, pow_limit // divisor)
                bits = target_to_compact(target)
                newest_time -= rng.randint(1, 1200) if height_offset else 0
                headers.append({'height': 55554 - height_offset, 'time': newest_time, 'bits': f'{bits:08x}'})
            actual = predict_dgw(headers, 55555)
            self.assertEqual(actual['predicted_nbits'], core_reference(headers), f'case {case}')

    def test_pow_limit_compact_encoding_matches_core_main_chain_parameter(self):
        self.assertEqual(target_to_compact(int(POW_LIMIT_HEX,16)),0x1e0fffff)
        self.assertLessEqual(compact_to_target('1e0fffff'),int(POW_LIMIT_HEX,16))
        self.assertEqual(compact_to_target('1e0fffff'),compact_to_target(target_to_compact(int(POW_LIMIT_HEX,16))))

if __name__=='__main__': unittest.main()
