# Copyright (c) 2026 btcdage / nextbtc2025
# Project: nextBTC Index Server
# Source: https://github.com/nextbtc2025/indexserver
# License: MIT (see LICENSE)

"""Explorer-only chain statistics and OP_RETURN memo decoding helpers."""
from decimal import Decimal

COIN = 100_000_000
MAX_STANDARD_OP_RETURN_BYTES = 80
# nextBTC consensus issuance parameters confirmed in the project specification.
INITIAL_SUBSIDY_SATS = 312_500_000  # 3.125 NBTC
SUBSIDY_HALVING_INTERVAL = 800_000
NOMINAL_MAX_SUPPLY_SATS = 5_000_000 * COIN


def block_subsidy_sats(height: int) -> int:
    """Return scheduled subsidy in satoshis for a non-genesis block.

    The custom genesis allocation (50 NBTC) is unspendable and is deliberately
    excluded from circulating/mined subsidy statistics. Normal subsidy begins
    with block 1 and halves at heights divisible by 800,000, matching Core's
    height // interval schedule. Integer right shift preserves satoshi rounding.
    """
    if isinstance(height, bool) or not isinstance(height, int) or height <= 0:
        return 0
    halvings = height // SUBSIDY_HALVING_INTERVAL
    if halvings >= 64:
        return 0
    return INITIAL_SUBSIDY_SATS >> halvings


def cumulative_scheduled_issuance_sats(height: int) -> int:
    """Sum scheduled non-genesis block subsidies from height 1 through height."""
    if isinstance(height, bool) or not isinstance(height, int) or height <= 0:
        return 0
    total = 0
    start = 1
    while start <= height:
        halvings = start // SUBSIDY_HALVING_INTERVAL
        end = min(height, (halvings + 1) * SUBSIDY_HALVING_INTERVAL - 1)
        subsidy = block_subsidy_sats(start)
        if subsidy:
            total += (end - start + 1) * subsidy
        start = end + 1
    return total


def maximum_scheduled_issuance_sats() -> int:
    """Exact lifetime scheduled subsidy, excluding the unspendable genesis allocation."""
    # Heights 1..799,999 receive the initial subsidy; later eras have 800,000
    # blocks each. Stop when integer-satoshi right shift reaches zero.
    total = (SUBSIDY_HALVING_INTERVAL - 1) * INITIAL_SUBSIDY_SATS
    for halvings in range(1, 64):
        subsidy = INITIAL_SUBSIDY_SATS >> halvings
        if not subsidy:
            break
        total += SUBSIDY_HALVING_INTERVAL * subsidy
    return total



def decode_op_return_script(script_hex):
    """Decode a single standard OP_RETURN push; never interpret arbitrary scripts as text."""
    if not isinstance(script_hex, str):
        return None
    try:
        raw = bytes.fromhex(script_hex)
    except ValueError:
        return None
    if len(raw) < 2 or raw[0] != 0x6A:
        return None
    pos = 1
    opcode = raw[pos]
    pos += 1
    if 1 <= opcode <= 75:
        size = opcode
    elif opcode == 0x4C:
        if pos >= len(raw): return None
        size = raw[pos]; pos += 1
    elif opcode == 0x4D:
        if pos + 2 > len(raw): return None
        size = int.from_bytes(raw[pos:pos+2], 'little'); pos += 2
    elif opcode == 0x4E:
        if pos + 4 > len(raw): return None
        size = int.from_bytes(raw[pos:pos+4], 'little'); pos += 4
    else:
        return None
    if size < 0 or pos + size != len(raw):
        return None
    payload = raw[pos:pos+size]
    if len(payload) > MAX_STANDARD_OP_RETURN_BYTES:
        return {'encoding':'hex','data_hex':payload.hex(),'byte_length':len(payload),
                'within_80_byte_limit':False,'text':None}
    try:
        text = payload.decode('utf-8')
        # Avoid control characters and terminal/UI spoofing in explorer display.
        if any(ord(ch) < 32 and ch not in '\t\n\r' for ch in text):
            raise UnicodeDecodeError('utf-8', payload, 0, len(payload), 'control character')
        encoding = 'utf-8'
    except UnicodeDecodeError:
        text = None
        encoding = 'hex'
    return {'encoding':encoding,'data_hex':payload.hex(),'byte_length':len(payload),
            'within_80_byte_limit':True,'text':text}


def address_balance_buckets(db,spendable_only=False):
    eligible="AND height>0 AND length(script)<=20000 AND substr(script,1,2)!='6a'" if spendable_only else ""
    rows = db.execute(f'''WITH balances AS (
        SELECT address, SUM(value) AS balance
        FROM outputs WHERE address IS NOT NULL AND spent_by IS NULL {eligible}
        GROUP BY address HAVING SUM(value) > 0
    ) SELECT
        SUM(CASE WHEN balance < ? THEN 1 ELSE 0 END) AS b0,
        SUM(CASE WHEN balance >= ? AND balance < ? THEN 1 ELSE 0 END) AS b1,
        SUM(CASE WHEN balance >= ? AND balance < ? THEN 1 ELSE 0 END) AS b2,
        SUM(CASE WHEN balance >= ? AND balance < ? THEN 1 ELSE 0 END) AS b3,
        SUM(CASE WHEN balance >= ? AND balance < ? THEN 1 ELSE 0 END) AS b4,
        SUM(CASE WHEN balance >= ? THEN 1 ELSE 0 END) AS b5,
        COUNT(*) AS nonzero_addresses
        FROM balances''', (COIN, COIN,10*COIN,10*COIN,100*COIN,100*COIN,1000*COIN,
                           1000*COIN,10000*COIN,10000*COIN)).fetchone()
    names = [d[0] for d in db.execute('SELECT 1').description] if False else None
    values = list(rows)
    return {f'bucket_{i}':int(values[i] or 0) for i in range(6)} | {
        'nonzero_balance_addresses':int(values[6] or 0)}
