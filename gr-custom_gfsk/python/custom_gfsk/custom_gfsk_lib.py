import zlib
import numpy as np

def crc32(data):
    return zlib.crc32(data).to_bytes(4, 'big')

def _slow_lfsr_scramble(data, seed=0x1FF):
    scrambled = bytearray()
    lfsr = seed
    for b in data:
        out_bit = 0
        for i in range(8):
            bit = (lfsr ^ (lfsr >> 5)) & 1
            lfsr = ((lfsr >> 1) | (bit << 8)) & 0x1FF
            out_bit = (out_bit << 1) | bit
        scrambled.append(b ^ out_bit)
    return bytes(scrambled)

_SCRAMBLE_KEY_56 = _slow_lfsr_scramble(bytes(56))
_SCRAMBLE_KEY_56_arr = np.frombuffer(_SCRAMBLE_KEY_56, dtype=np.uint8).copy()

_SCRAMBLE_KEY_42 = _slow_lfsr_scramble(bytes(42))
_SCRAMBLE_KEY_42_arr = np.frombuffer(_SCRAMBLE_KEY_42, dtype=np.uint8).copy()

def lfsr_scramble(data, seed=0x1FF):
    data_arr = np.frombuffer(data, dtype=np.uint8)
    if seed == 0x1FF:
        if len(data_arr) == 56:
            return np.bitwise_xor(data_arr, _SCRAMBLE_KEY_56_arr).tobytes()
        elif len(data_arr) == 42:
            return np.bitwise_xor(data_arr, _SCRAMBLE_KEY_42_arr).tobytes()
    return _slow_lfsr_scramble(data, seed)

def parity_2d_encode(data, rows=7, cols=6):
    # data is 42 bytes (7 * 6)
    if len(data) != rows * cols:
        raise ValueError(f"Data length {len(data)} must be {rows*cols}")
    
    matrix = np.frombuffer(data, dtype=np.uint8).reshape((rows, cols))
    
    # Compute row parity (XOR across columns)
    row_p = np.bitwise_xor.reduce(matrix, axis=1) # shape (12,)
    # Compute column parity (XOR across rows)
    col_p = np.bitwise_xor.reduce(matrix, axis=0) # shape (11,)
    # Compute overall parity
    overall_p = np.bitwise_xor.reduce(row_p)
    overall_p = np.array([overall_p], dtype=np.uint8)
    
    # Concatenate: data + row_p + col_p + overall_p
    # Total length: 132 + 12 + 11 + 1 = 156 bytes
    return bytes(data) + bytes(row_p) + bytes(col_p) + bytes(overall_p)

def parity_2d_decode(data, rows=7, cols=6):
    # expected len = rows*cols + rows + cols + 1 = 42+7+6+1 = 56
    if len(data) != rows*cols + rows + cols + 1:
        return b"", False # invalid length
        
    matrix_expected_len = rows*cols
    matrix_flat = np.frombuffer(data[:matrix_expected_len], dtype=np.uint8).copy()
    matrix = matrix_flat.reshape((rows, cols))
    
    rx_row_p = np.frombuffer(data[matrix_expected_len:matrix_expected_len+rows], dtype=np.uint8)
    rx_col_p = np.frombuffer(data[matrix_expected_len+rows:matrix_expected_len+rows+cols], dtype=np.uint8)
    # ignore overall parity for basic correction
    
    calc_row_p = np.bitwise_xor.reduce(matrix, axis=1)
    calc_col_p = np.bitwise_xor.reduce(matrix, axis=0)
    
    row_errors = np.where(rx_row_p != calc_row_p)[0]
    col_errors = np.where(rx_col_p != calc_col_p)[0]
    
    # Attempt simple single byte correction if 1 row and 1 col error
    if len(row_errors) == 1 and len(col_errors) == 1:
        r = row_errors[0]
        c = col_errors[0]
        # The erroneous byte is at (r, c).
        # We can fix it by XORing it with the difference between rx and calc parity
        diff = rx_row_p[r] ^ calc_row_p[r]
        matrix[r, c] ^= diff
        return bytes(matrix.flatten()), True
    elif len(row_errors) == 0 and len(col_errors) == 0:
        return bytes(matrix.flatten()), True
    else:
        # Cannot correct multiple errors simply with standard 2D parity, output as is and hope
        return bytes(matrix.flatten()), False


def _slow_hamming_8_4_encode(nibble):
    d = [(nibble >> i) & 1 for i in range(4)][::-1]
    p1 = d[0] ^ d[1] ^ d[3]
    p2 = d[0] ^ d[2] ^ d[3]
    p3 = d[1] ^ d[2] ^ d[3]
    bits = [p1, p2, d[0], p3, d[1], d[2], d[3]]
    p0 = sum(bits) % 2
    return (p0 << 7) | (p1 << 6) | (p2 << 5) | (d[0] << 4) | (p3 << 3) | (d[1] << 2) | (d[2] << 1) | d[3]

_HAMMING_ENC_LUT = np.zeros(16, dtype=np.uint8)
for i in range(16):
    _HAMMING_ENC_LUT[i] = _slow_hamming_8_4_encode(i)

def encode_hamming(data):
    data_arr = np.frombuffer(data, dtype=np.uint8)
    high_nibbles = data_arr >> 4
    low_nibbles = data_arr & 0x0F
    
    encoded_high = _HAMMING_ENC_LUT[high_nibbles]
    encoded_low = _HAMMING_ENC_LUT[low_nibbles]
    
    out = np.empty(len(data_arr)*2, dtype=np.uint8)
    out[0::2] = encoded_high
    out[1::2] = encoded_low
    return out.tobytes()

def _slow_hamming_8_4_decode(byte_val):
    # Returns decoded nibble and error flag
    bits = [(byte_val >> i) & 1 for i in range(8)][::-1]
    p0, p1, p2, d1, p3, d2, d3, d4 = bits
    
    s1 = p1 ^ d1 ^ d2 ^ d4
    s2 = p2 ^ d1 ^ d3 ^ d4
    s3 = p3 ^ d2 ^ d3 ^ d4
    
    syndrome = (s1 << 2) | (s2 << 1) | s3
    
    # overall parity check
    calc_p0 = sum(bits[1:]) % 2
    parity_error = p0 != calc_p0
    
    if syndrome == 0:
        if parity_error: 
            pass # P0 itself is flipped, data is fine
        return (d1 << 3) | (d2 << 2) | (d3 << 1) | d4, 0 # no error
    else:
        # Error exists
        if parity_error: # Single bit error
            error_pos = {
                1: 7, # p3
                2: 6, # p2
                3: 5, # d3
                4: 4, # p1
                5: 3, # d2
                6: 2, # d1
                7: 1  # d4
            }
            if syndrome in error_pos:
                pos = error_pos[syndrome]
                # Flip the bit in our bits list
                bits[8-pos] ^= 1
                return (bits[3] << 3) | (bits[5] << 2) | (bits[6] << 1) | bits[7], 1 # Corrected
        return (d1 << 3) | (d2 << 2) | (d3 << 1) | d4, 2 # Double error detected

_HAMMING_DEC_LUT = np.zeros(256, dtype=np.uint8)
for i in range(256):
    nib, err = _slow_hamming_8_4_decode(i)
    _HAMMING_DEC_LUT[i] = nib

def decode_hamming(data):
    data_arr = np.frombuffer(data, dtype=np.uint8)
    high_bytes = data_arr[0::2]
    low_bytes = data_arr[1::2]
    
    decoded_high = _HAMMING_DEC_LUT[high_bytes]
    decoded_low = _HAMMING_DEC_LUT[low_bytes]
    
    final_bytes = (decoded_high << 4) | decoded_low
    return final_bytes.tobytes()

# ----------------- NUCLEAR FEC OVERRIDE ----------------- #
def encode_rep3(data):
    """ Triples data payload cleanly using continuous block interleaving. """
    data_arr = np.frombuffer(data, dtype=np.uint8)
    return np.concatenate((data_arr, data_arr, data_arr)).tobytes()

def decode_rep3(data):
    """
    Evaluates 3 duplicate block-interleaved streams dynamically.
    Recovers up to 33% absolute bit flip corruption via Majority Voting.
    """
    data_arr = np.frombuffer(data, dtype=np.uint8)
    N = len(data_arr) // 3
    A = data_arr[:N]
    B = data_arr[N:2*N]
    C = data_arr[2*N:3*N]
    
    # Majority Truth Table: (A AND B) OR (B AND C) OR (A AND C)
    AB = np.bitwise_and(A, B)
    BC = np.bitwise_and(B, C)
    AC = np.bitwise_and(A, C)
    res = np.bitwise_or(AB, np.bitwise_or(BC, AC))
    return res.tobytes()
# -------------------------------------------------------- #

def block_interleave(data, rows=32, cols=28):
    # data 112 bytes = 896 bits. 32 * 28 = 896
    bits = np.unpackbits(np.frombuffer(data, dtype=np.uint8))
    matrix = bits.reshape((rows, cols))
    interleaved_bits = matrix.T.flatten()
    return np.packbits(interleaved_bits).tobytes()

def block_deinterleave(data, rows=32, cols=28):
    bits = np.unpackbits(np.frombuffer(data, dtype=np.uint8))
    # It was T, so it is (cols, rows)
    matrix = bits.reshape((cols, rows))
    deinterleaved_bits = matrix.T.flatten()
    return np.packbits(deinterleaved_bits).tobytes()
    
# Constants
SYNC_WORD = b'\x93\x0B\x51\xDE\x93\x0B\x51\xDE' # 64 bits
SYNC_BITS = np.unpackbits(np.frombuffer(SYNC_WORD, dtype=np.uint8))
PREAMBLE = b'\x55' * 8
