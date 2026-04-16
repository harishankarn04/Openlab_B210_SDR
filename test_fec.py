import zlib
import numpy as np

def crc32(data):
    return zlib.crc32(data).to_bytes(4, 'big')

def lfsr_scramble(data, seed=0x1FF):
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

# Hamming(8,4) SECDED encoding
def hamming_8_4_encode(nibble):
    # nibble is 4 bits: d1, d2, d3, d4
    d = [(nibble >> i) & 1 for i in range(4)][::-1] # MSB first: d1 = d[0]
    p1 = d[0] ^ d[1] ^ d[3]
    p2 = d[0] ^ d[2] ^ d[3]
    p3 = d[1] ^ d[2] ^ d[3]
    # Data: p1 p2 d1 p3 d2 d3 d4
    # Indices: 1, 2, 3, 4, 5, 6, 7
    # Overall parity p0
    bits = [p1, p2, d[0], p3, d[1], d[2], d[3]]
    p0 = sum(bits) % 2
    return (p0 << 7) | (p1 << 6) | (p2 << 5) | (d[0] << 4) | (p3 << 3) | (d[1] << 2) | (d[2] << 1) | d[3]

def encode_bytes(data):
    encoded = bytearray()
    for b in data:
        nibble1 = (b >> 4) & 0x0F
        nibble2 = b & 0x0F
        encoded.append(hamming_8_4_encode(nibble1))
        encoded.append(hamming_8_4_encode(nibble2))
    return bytes(encoded)

def block_interleave(data, rows, cols):
    # data is bytes, we'll interleave bits
    bits = np.unpackbits(np.frombuffer(data, dtype=np.uint8))
    # padding if necessary
    if len(bits) % (rows * cols) != 0:
        pad = (rows * cols) - (len(bits) % (rows * cols))
        bits = np.concatenate((bits, np.zeros(pad, dtype=np.uint8)))
    # reshape and transpose
    matrix = bits.reshape((rows, cols))
    interleaved = matrix.T.flatten()
    return np.packbits(interleaved).tobytes()

# Test
payload = b"A" * 128
checksum = crc32(payload)
scrambled = lfsr_scramble(payload + checksum)
encoded = encode_bytes(scrambled)
interleaved = block_interleave(encoded, 33, 64) # 264 bytes = 2112 bits. 33 * 64 = 2112 !

print("Payload:", len(payload))
print("Checksum:", len(checksum))
print("Scrambled:", len(scrambled))
print("Encoded:", len(encoded))
print("Interleaved:", len(interleaved))
