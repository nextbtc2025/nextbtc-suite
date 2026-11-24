# Copyright (c) 2026 btcdage / nextbtc2025
# Project: nextBTC Index Server
# Source: https://github.com/nextbtc2025/indexserver
# License: MIT (see LICENSE)

import sqlite3
from explorer_chain_data import decode_op_return_script, address_balance_buckets, COIN


def test_decode_op_return_utf8_and_hex():
    payload='NBTC memo'.encode()
    script='6a'+bytes([len(payload)]).hex()+payload.hex()
    memo=decode_op_return_script(script)
    assert memo['text']=='NBTC memo'
    assert memo['byte_length']==len(payload)
    assert memo['encoding']=='utf-8'


def test_decode_op_return_rejects_non_op_return_and_malformed_push():
    assert decode_op_return_script('51') is None
    assert decode_op_return_script('6a4c') is None
    assert decode_op_return_script('6a02aa') is None


def test_decode_op_return_large_payload_is_not_text():
    payload=b'x'*81
    script='6a4c'+bytes([len(payload)]).hex()+payload.hex()
    memo=decode_op_return_script(script)
    assert memo['text'] is None
    assert memo['within_80_byte_limit'] is False


def test_address_balance_buckets_use_exact_boundaries_and_exclude_zero():
    db=sqlite3.connect(':memory:')
    db.execute('CREATE TABLE outputs(address TEXT,value INTEGER,spent_by TEXT)')
    vals=[('a',1),('b',COIN-1),('c',COIN),('d',10*COIN),('e',100*COIN),
          ('f',1000*COIN),('g',10000*COIN),('z',0)]
    db.executemany('INSERT INTO outputs VALUES(?,?,NULL)',vals)
    result=address_balance_buckets(db)
    assert result=={'bucket_0':2,'bucket_1':1,'bucket_2':1,'bucket_3':1,
                    'bucket_4':1,'bucket_5':1,'nonzero_balance_addresses':7}


def test_address_balance_buckets_sum_multiple_utxos_per_address():
    db=sqlite3.connect(':memory:')
    db.execute('CREATE TABLE outputs(address TEXT,value INTEGER,spent_by TEXT)')
    db.executemany('INSERT INTO outputs VALUES(?,?,NULL)',[('a',COIN//2),('a',COIN//2),('b',1)])
    result=address_balance_buckets(db)
    assert result['bucket_0']==1
    assert result['bucket_1']==1
    assert result['nonzero_balance_addresses']==2


def test_nextbtc_halving_subsidy_uses_integer_satoshi_rounding():
    from explorer_chain_data import block_subsidy_sats, INITIAL_SUBSIDY_SATS, SUBSIDY_HALVING_INTERVAL
    assert INITIAL_SUBSIDY_SATS == 312_500_000
    assert SUBSIDY_HALVING_INTERVAL == 800_000
    assert block_subsidy_sats(0) == 0  # custom unspendable genesis allocation is separate
    assert block_subsidy_sats(1) == 312_500_000
    assert block_subsidy_sats(799_999) == 312_500_000
    assert block_subsidy_sats(800_000) == 156_250_000
    assert block_subsidy_sats(1_600_000) == 78_125_000
    assert block_subsidy_sats(24_000_000) == 0


def test_nextbtc_cumulative_issuance_and_lifetime_schedule():
    from explorer_chain_data import cumulative_scheduled_issuance_sats, maximum_scheduled_issuance_sats
    assert cumulative_scheduled_issuance_sats(0) == 0
    assert cumulative_scheduled_issuance_sats(1) == 312_500_000
    assert cumulative_scheduled_issuance_sats(799_999) == 799_999 * 312_500_000
    assert cumulative_scheduled_issuance_sats(800_000) == 799_999 * 312_500_000 + 156_250_000
    assert maximum_scheduled_issuance_sats() == 499_999_678_700_000
    assert cumulative_scheduled_issuance_sats(99_999_999) == maximum_scheduled_issuance_sats()
