# Copyright (c) 2026 btcdage / nextbtc2025
# Project: nextBTC Index Server
# Source: https://github.com/nextbtc2025/indexserver
# License: MIT (see LICENSE)

"""Explorer-only calculations. DWG implementation mirrors nextBTC Core src/pow.cpp."""
from decimal import Decimal

POW_LIMIT_HEX = '00000fffffffffffffffffffffffffffffffffffffffffffffffffffffffffff'
INSTANT_MINE_END_HEIGHT = 55555
PAST_BLOCKS = 24


def read_header_range(rpc, first_height, last_height):
    """Fetch a bounded range newest first and reject mixed branches or RPC results."""
    heights = list(range(last_height, first_height - 1, -1))

    def fetch(method, params):
        if callable(getattr(rpc, 'batch', None)):
            return rpc.batch(method, params, batch_size=100)
        return [rpc.call(method, *args) for args in params]

    hashes = fetch('getblockhash', [[height] for height in heights])
    headers = fetch('getblockheader', [[block_hash, True] for block_hash in hashes])
    if len(headers) != len(hashes) or len(hashes) != len(heights):
        raise ValueError('Core returned an incomplete header range')
    rows = []
    for i, (height, block_hash, header) in enumerate(zip(heights, hashes, headers)):
        if header.get('height') != height or header.get('hash') != block_hash:
            raise ValueError(f'Core returned an inconsistent header at height {height}')
        if i + 1 < len(hashes) and header.get('previousblockhash') != hashes[i + 1]:
            raise ValueError('Active chain changed during header range query')
        rows.append({'height':height, 'hash':block_hash, 'time':int(header['time']),
                     'bits':str(header['bits']).lower()})
    if rpc.call('getblockhash', last_height) != hashes[0]:
        raise ValueError('Active chain changed during header range query')
    return rows


def network_series(headers, limit):
    """Difficulty and Core-style rolling work/time estimates on contiguous headers."""
    reference = compact_to_target('1d00ffff')
    targets = [compact_to_target(header['bits']) for header in headers]
    work = [(1 << 256) // (target + 1) for target in targets]
    rows = []
    for i, header in enumerate(headers[:limit]):
        intervals = min(PAST_BLOCKS, len(headers) - i - 1)
        times = [h['time'] for h in headers[i:i + intervals + 1]]
        elapsed = max(times) - min(times)
        # Work is the chainwork difference between the ends. The oldest
        # header supplies a timestamp, but its proof precedes this interval.
        rate = sum(work[i:i + intervals]) / elapsed if elapsed else None
        change = (targets[i + 1] / targets[i] - 1) * 100 if i + 1 < len(headers) else None
        rows.append({**header, 'difficulty':reference / targets[i], 'difficulty_change_percent':change,
                     'hashrate_hps':rate, 'hashrate_window_blocks':intervals,
                     'hashrate_timespan_seconds':elapsed})
    return rows

def compact_to_target(bits):
    bits = int(str(bits), 16) if isinstance(bits, str) else int(bits)
    size = bits >> 24
    word = bits & 0x007fffff
    if size <= 3:
        target = word >> (8 * (3 - size))
    else:
        target = word << (8 * (size - 3))
    negative = bool(word and (bits & 0x00800000))
    overflow = bool(word and ((size > 34) or (word > 0xff and size > 33) or (word > 0xffff and size > 32)))
    if negative or overflow or target <= 0:
        raise ValueError('Invalid compact target in canonical block header')
    return target

def target_to_compact(value):
    if value <= 0:
        return 0
    size = (value.bit_length() + 7) // 8
    compact = value << (8 * (3 - size)) if size <= 3 else value >> (8 * (size - 3))
    if compact & 0x00800000:
        compact >>= 8
        size += 1
    return (size << 24) | (compact & 0x007fffff)

def predict_dgw(headers_newest_first, candidate_height, target_spacing=150, pow_limit_hex=POW_LIMIT_HEX):
    """Return Core-equivalent next nBits and explanatory fields.

    headers must start at pindexLast and contain up to 24 canonical headers.
    The loop intentionally sums 23 timestamp deltas for a full 24-block window,
    while Core sets target timespan to CountBlocks * target_spacing.
    """
    pow_limit = int(str(pow_limit_hex), 16)
    if pow_limit <= 0:
        raise ValueError('powLimit must be positive')
    if candidate_height < INSTANT_MINE_END_HEIGHT:
        initial_bits = target_to_compact(pow_limit)
        initial_target = compact_to_target(initial_bits)
        current_target = compact_to_target(headers_newest_first[0]['bits']) if headers_newest_first else None
        change = (current_target / initial_target - 1) * 100 if current_target is not None else None
        return {'phase':'instant_mine','candidate_height':candidate_height,
                'window_blocks':0,'actual_timespan':None,'target_timespan':None,
                'predicted_nbits':f'{initial_bits:08x}',
                'predicted_target':format(initial_target,'064x'),'change_percent':change,
                'clamped':False,'available':True}
    if candidate_height - 1 < PAST_BLOCKS:
        initial_bits = target_to_compact(pow_limit)
        initial_target = compact_to_target(initial_bits)
        return {'phase':'early_chain','candidate_height':candidate_height,'window_blocks':0,
                'predicted_nbits':f'{initial_bits:08x}','predicted_target':format(initial_target,'064x'),
                'change_percent':0.0,'clamped':False,'available':True}
    if len(headers_newest_first) < PAST_BLOCKS:
        return {'available':False,'reason':'DWG 24-block history is not available'}
    selected=headers_newest_first[:PAST_BLOCKS]
    count=0
    avg=0
    prev_time=0
    actual=0
    for h in selected:
        count += 1
        target=compact_to_target(h['bits'])
        if count == 1:
            avg=target
        else:
            # Mirrors: ((PastDifficultyAveragePrev * (CountBlocks - 1)) + target) / CountBlocks
            avg=(avg*(count-1)+target)//count
        if prev_time > 0:
            actual += prev_time-int(h['time'])
        prev_time=int(h['time'])
    target_span=count*int(target_spacing)
    lower=target_span//3
    upper=target_span*3
    clamped=max(lower,min(actual,upper))
    new_target=(avg*clamped)//target_span
    if new_target > pow_limit:
        new_target=pow_limit
    nbits=target_to_compact(new_target)
    # Core consensus returns compact nBits. Display values and percentage must
    # use the target decoded from that compact value, not the pre-encoding int.
    encoded_target=compact_to_target(nbits)
    current_target=compact_to_target(selected[0]['bits'])
    change=(Decimal(current_target)/Decimal(encoded_target)-1)*Decimal(100) if encoded_target else Decimal(0)
    return {'available':True,'phase':'dgw_v3','candidate_height':candidate_height,
            'window_blocks':count,'timestamp_intervals':max(0,count-1),
            'actual_timespan':actual,'clamped_timespan':clamped,
            'target_timespan':target_span,'lower_bound':lower,'upper_bound':upper,
            'clamped':clamped != actual,'predicted_nbits':f'{nbits:08x}',
            'predicted_target':format(encoded_target,'064x'),'calculated_target':format(new_target,'064x'),
            'current_nbits':str(selected[0]['bits']).lower().removeprefix('0x').zfill(8),
            'change_percent':float(change),'average_target':format(avg,'064x')}


def verify_template_bits(prediction, template, expected_height, expected_parent=None):
    """Compare the predicted compact target to Core's getblocktemplate result."""
    if not isinstance(template, dict):
        return {'available':False,'matched':None,'reason':'Malformed Core template'}
    try: template_height=int(template.get('height',-1))
    except (TypeError,ValueError):
        return {'available':False,'matched':None,'reason':'Invalid Core template height'}
    if template_height != int(expected_height):
        return {'available':False,'matched':None,'reason':'Core template height does not match current tip'}
    if expected_parent is not None and template.get('previousblockhash') != expected_parent:
        return {'available':False,'matched':None,'reason':'Core template parent does not match the observed tip'}
    bits=str(template.get('bits','')).lower().removeprefix('0x')
    if len(bits)!=8 or any(c not in '0123456789abcdef' for c in bits) or bits=='00000000':
        return {'available':False,'matched':None,'reason':'Core returned invalid template bits'}
    if not isinstance(prediction,dict) or not prediction.get('available') or not prediction.get('predicted_nbits'):
        return {'available':False,'matched':None,'reason':'Explorer prediction is unavailable'}
    return {'available':True,'matched':prediction['predicted_nbits']==bits,
            'template_height':template_height,'template_nbits':bits,
            'predicted_nbits':prediction['predicted_nbits']}
