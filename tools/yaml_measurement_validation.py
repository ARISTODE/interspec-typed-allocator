"""Fail-closed acceptance for the fixed YAML workload. No application execution."""
import functools
import hashlib
import re

MODES = ('native', 'rlbox_only', 'tracked_no_check', 'extended_sp3')
DOCUMENT_SHA256 = '76f5fb2187018406caccec14d86af59e2eb1960df8aa4d852335076a9627923f'
FIELDS = set('mode iterations input_bytes events scalars scalar_bytes hash checks elapsed_ns'.split())

def integer(value, minimum=0, maximum=(1 << 64) - 1):
    if isinstance(value, bool) or not re.fullmatch(r'[0-9]+', str(value)):
        raise ValueError('invalid integer')
    result = int(value)
    if result < minimum or result > maximum:
        raise ValueError('integer outside supported range')
    return result

def parse_line(stdout):
    lines = [line for line in stdout.splitlines() if line.startswith('YAML_BENCH ')]
    if len(lines) != 1:
        raise ValueError('expected exactly one YAML_BENCH line')
    row = {}
    for token in lines[0].split()[1:]:
        if token.count('=') != 1:
            raise ValueError('malformed field')
        key, value = token.split('=')
        if key in row:
            raise ValueError('duplicate field')
        row[key] = value
    if set(row) != FIELDS or row['mode'] not in MODES:
        raise ValueError('invalid fields or mode')
    for key in FIELDS - {'mode', 'hash'}:
        integer(row[key], 1 if key in ('iterations', 'elapsed_ns') else 0)
    integer(row['iterations'], 1, (1 << 32) - 1)
    integer(row['input_bytes'], 0, (1 << 32) - 1)
    if not re.fullmatch('[0-9a-f]{16}', row['hash']):
        raise ValueError('invalid hash')
    return row

def document():
    # Reconstruct the specified workload independently, without calling generator.
    pairs = [b'key%03d: ' % i + bytes([97 + i % 26]) * 4000 + b'\n' for i in range(256)]
    prefix = b'---\n' + b''.join(pairs)
    comment_length = 1048576 - len(prefix) - 4
    return prefix + b'#' + b'x' * (comment_length - 2) + b'\n...\n'

@functools.lru_cache(maxsize=16)
def expected_hash(iterations):
    iterations = integer(iterations, 1, (1 << 32) - 1)
    # Independently reconstructed by the retained C++ specification oracle,
    # not inferred from cross-mode agreement. Input is separately byte-checked.
    # Avoid a billion Python byte steps for the declared publication workload.
    known = {1: 'd5750b6fb7ce77eb', 2: 'ee078a6ead8e6373',
             1000: 'fc5395e206af4643'}
    if iterations in known:
        return known[iterations]
    # YAML emits keys and values alternately. FNV state persists across parses.
    payload = b''.join(b'key%03d' % i + bytes([97 + i % 26]) * 4000 for i in range(256))
    state = 1469598103934665603
    for _ in range(iterations):
        for byte in payload:
            state = ((state ^ byte) * 1099511628211) & 0xffffffffffffffff
    return '%016x' % state

def validate_result(row, mode, iterations, input_data):
    # Reparse serialized dictionaries as well, so callers cannot skip syntax checks.
    row = parse_line('YAML_BENCH ' + ' '.join('%s=%s' % item for item in row.items()))
    iterations = integer(iterations, 1, (1 << 32) - 1)
    if mode not in MODES or row['mode'] != mode:
        raise ValueError('reported mode differs from requested mode')
    if input_data != document() or hashlib.sha256(input_data).hexdigest() != DOCUMENT_SHA256:
        raise ValueError('input differs from fixed workload')
    expected = dict(iterations=iterations, input_bytes=len(input_data),
                    events=518 * iterations, scalars=512 * iterations,
                    scalar_bytes=1025536 * iterations,
                    checks=512 * iterations if mode == 'extended_sp3' else 0)
    for key, value in expected.items():
        if integer(row[key]) != value:
            raise ValueError('unexpected ' + key)
    if row['hash'] != expected_hash(iterations):
        raise ValueError('unexpected scalar content hash')
    return row

def validate_grid(samples, repetitions):
    repetitions = integer(repetitions, 1)
    expected = {(rep, mode) for rep in range(repetitions) for mode in MODES}
    seen = set()
    for row in samples:
        if set(row) != {'workload', 'mode', 'repetition', 'total_ns'}:
            raise ValueError('invalid sample fields')
        key = (integer(row['repetition']), row['mode'])
        if key not in expected or key in seen or row['workload'] != 'yaml_parse_1mb':
            raise ValueError('duplicate, unknown or out-of-range cell')
        integer(row['total_ns'], 1)
        seen.add(key)
    if seen != expected:
        raise ValueError('incomplete grid')
