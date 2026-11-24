# Copyright (c) 2026 btcdage / nextbtc2025
# Project: nextBTC Index Server
# Source: https://github.com/nextbtc2025/indexserver
# License: MIT (see LICENSE)

import configparser
import tempfile
import time
import unittest
from pathlib import Path

from indexer import Indexer
from mempool import MempoolTracker
try:
    from server import make_app
except ImportError:
    make_app = None


class NullRpc:
    def call(self, method, *params):
        raise AssertionError(f"Unexpected RPC call: {method}")


class MempoolRpc:
    def __init__(self, transactions):
        self.transactions = transactions

    def call(self, method, *params):
        if method == "getrawmempool":
            return {txid: {"time": 1_800_000_000, "vsize": 120, "fees": {"base":"0.00000100"}} for txid in self.transactions}
        if method == "getrawtransaction":
            return self.transactions[params[0]]
        raise AssertionError(f"Unexpected RPC call: {method}")


class FakeMempool:
    def get(self):
        return {
            "txs": {}, "spends": {}, "received": {}, "activity": {},
            "updated": time.time(), "error": None,
        }


class FakeIndexer:
    def __init__(self):
        self.flow_calls = 0

    def tip(self):
        return {"height": 100, "hash": "a" * 64}

    def address_info(self, address, current_height):
        return {"address": address, "utxos": []}

    def history(self, address, limit=50, offset=0):
        return [{
            "txid": "b" * 64, "height": 100, "timestamp": 1_800_000_000,
            "received_sats": 500, "sent_sats": 0, "net_sats": 500,
            "unconfirmed": False,
        }]

    def transaction_flows(self, txids, snapshot=None):
        self.flow_calls += 1
        return {txid: {"input_addresses": ["bc1q" + "c" * 38],
                       "output_addresses": ["bc1q" + "d" * 38],
                       "inputs": [{"txid": "e" * 64, "vout": 0, "address": "bc1q" + "c" * 38, "value_sats": 900}],
                       "outputs": [{"vout": 0, "address": "bc1q" + "d" * 38, "value_sats": 850}]}
                for txid in txids}


class TestTransactionFlow(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "index.db"
        self.indexer = Indexer(self.db_path, NullRpc())

    def tearDown(self):
        self.indexer.db.close()
        self.temp.cleanup()

    def test_confirmed_inputs_and_outputs_resolved_from_existing_outputs(self):
        txid = "1" * 64
        with self.indexer.db:
            self.indexer.db.execute(
                "INSERT INTO outputs(txid,vout,height,value,script,address,spent_by,spent_height) VALUES(?,?,?,?,?,?,?,?)",
                ("2" * 64, 0, 90, 700, "51", "bc1q" + "a" * 38, txid, 100),
            )
            self.indexer.db.execute(
                "INSERT INTO outputs(txid,vout,height,value,script,address,spent_by,spent_height) VALUES(?,?,?,?,?,?,?,?)",
                ("3" * 64, 1, 91, 300, "51", "bc1q" + "b" * 38, txid, 100),
            )
            self.indexer.db.execute(
                "INSERT INTO outputs(txid,vout,height,value,script,address) VALUES(?,?,?,?,?,?)",
                (txid, 0, 100, 950, "51", "bc1q" + "e" * 38),
            )
        result = self.indexer.transaction_flows([txid])[txid]
        self.assertEqual(set(result["input_addresses"]), {"bc1q" + "a" * 38, "bc1q" + "b" * 38})
        self.assertEqual(result["output_addresses"], ["bc1q" + "e" * 38])
        self.assertEqual({x["value_sats"] for x in result["inputs"]}, {700, 300})
        self.assertEqual(result["outputs"][0]["value_sats"], 950)

    def test_mempool_parent_child_inputs_resolve_from_snapshot_and_index(self):
        prev_txid = "4" * 64
        parent = "5" * 64
        child = "6" * 64
        with self.indexer.db:
            self.indexer.db.execute(
                "INSERT INTO outputs(txid,vout,height,value,script,address) VALUES(?,?,?,?,?,?)",
                (prev_txid, 0, 99, 1000, "51", "bc1q" + "f" * 38),
            )
        txs = {
            parent: {
                "txid": parent,
                "vin": [{"txid": prev_txid, "vout": 0}],
                "vout": [{"n": 0, "value": 0.000009, "scriptPubKey": {"hex": "0014", "address": "bc1q" + "g" * 38}}],
            },
            child: {
                "txid": child,
                "vin": [{"txid": parent, "vout": 0}],
                "vout": [{"n": 0, "value": 0.000008, "scriptPubKey": {"hex": "0014", "address": "bc1q" + "h" * 38}}],
            },
        }
        tracker = MempoolTracker(MempoolRpc(txs), max_txs=20)
        tracker.refresh()
        result = self.indexer.transaction_flows([parent, child], tracker.get())
        self.assertEqual(result[parent]["input_addresses"], ["bc1q" + "f" * 38])
        self.assertEqual(result[parent]["output_addresses"], ["bc1q" + "g" * 38])
        self.assertEqual(result[child]["input_addresses"], ["bc1q" + "g" * 38])
        self.assertEqual(result[child]["output_addresses"], ["bc1q" + "h" * 38])
        self.assertEqual(result[parent]["outputs"][0]["value_sats"], 900)
        self.assertEqual(result[child]["inputs"][0]["value_sats"], 900)
        self.assertEqual(result[child]["outputs"][0]["value_sats"], 800)

    def test_mempool_non_address_parent_output_is_resolved_for_child_input(self):
        parent = "7" * 64
        child = "8" * 64
        txs = {
            parent: {
                "txid": parent,
                "vin": [{"txid": "9" * 64, "vout": 0}],
                "vout": [{"n": 0, "value": 0.00001000,
                          "scriptPubKey": {"hex": "6a04deadbeef"}}],
            },
            child: {
                "txid": child,
                "vin": [{"txid": parent, "vout": 0}],
                "vout": [{"n": 0, "value": 0.00000900,
                          "scriptPubKey": {"hex": "0014", "address": "bc1q" + "j" * 38}}],
            },
        }
        tracker = MempoolTracker(MempoolRpc(txs), max_txs=20)
        tracker.refresh()
        result = self.indexer.transaction_flows([child], tracker.get())[child]
        self.assertEqual(result["input_count"], 1)
        self.assertEqual(result["inputs"][0]["txid"], parent)
        self.assertIsNone(result["inputs"][0]["address"])
        self.assertEqual(result["inputs"][0]["value_sats"], 1000)
        self.assertEqual(result["inputs_unresolved"], 0)

    def test_flow_arrays_report_truncation_instead_of_silent_partial_data(self):
        txid = "a" * 64
        with self.indexer.db:
            for i in range(300):
                self.indexer.db.execute(
                    "INSERT INTO outputs(txid,vout,height,value,script,address,spent_by,spent_height) VALUES(?,?,?,?,?,?,?,?)",
                    (f"{i:064x}", 0, 90, 1, "51", "bc1q" + "a" * 38, txid, 100),
                )
            for i in range(300):
                self.indexer.db.execute(
                    "INSERT INTO outputs(txid,vout,height,value,script,address) VALUES(?,?,?,?,?,?)",
                    (txid, i, 100, 1, "51", "bc1q" + "b" * 38),
                )
        flow = self.indexer.transaction_flows([txid])[txid]
        self.assertEqual(flow["input_count"], 300)
        self.assertEqual(flow["output_count"], 300)
        self.assertEqual(len(flow["inputs"]), 256)
        self.assertEqual(len(flow["outputs"]), 256)
        self.assertTrue(flow["inputs_truncated"])
        self.assertTrue(flow["outputs_truncated"])

    @unittest.skipIf(make_app is None, "Flask/Waitress dependencies are not installed in this test environment")
    def test_history_flow_is_opt_in_and_legacy_response_stays_compact(self):
        indexer = FakeIndexer()
        config = configparser.ConfigParser()
        config.read_dict({
            "server": {"cors_origins": "null"},
            "fees": {"fallback_sat_vb": "1.0", "mempool_min_samples": "5"},
        })
        app = make_app(config, indexer, NullRpc(), {"remote_height": 100, "error": None}, FakeMempool())
        client = app.test_client()
        address = "bc1q" + "a" * 38
        legacy = client.get(f"/api/v1/history/{address}?limit=10")
        self.assertEqual(legacy.status_code, 200)
        self.assertNotIn("input_addresses", legacy.get_json()["transactions"][0])
        self.assertEqual(indexer.flow_calls, 0)

        enriched = client.get(f"/api/v1/history/{address}?limit=10&include_flow=1")
        self.assertEqual(enriched.status_code, 200)
        row = enriched.get_json()["transactions"][0]
        self.assertEqual(row["input_addresses"], ["bc1q" + "c" * 38])
        self.assertEqual(row["output_addresses"], ["bc1q" + "d" * 38])
        self.assertEqual(row["inputs"][0]["value_sats"], 900)
        self.assertEqual(row["outputs"][0]["value_sats"], 850)
        self.assertEqual(indexer.flow_calls, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
