import custom_gfsk_lib as g
import sys
import os

def test_flow():
    payload = os.urandom(128)
    
    # 1. CRC
    crc = g.crc32(payload)
    block1 = payload + crc
    assert len(block1) == 132
    
    # 2. 2D Parity
    block2 = g.parity_2d_encode(block1)
    assert len(block2) == 156
    
    # 3. Scramble
    block3 = g.lfsr_scramble(block2)
    assert len(block3) == 156
    
    # 4. Hamming
    block4 = g.encode_hamming(block3)
    assert len(block4) == 312
    
    # 5. Interleave
    block5 = g.block_interleave(block4)
    assert len(block5) == 312
    
    # ------------------
    # Reverse!
    # ------------------
    
    # 1. Deinterleave
    rx_block4 = g.block_deinterleave(block5)
    assert rx_block4 == block4
    
    # 2. Hamming Decode
    rx_block3 = g.decode_hamming(rx_block4)
    assert rx_block3 == block3
    
    # 3. Descramble
    rx_block2 = g.lfsr_scramble(rx_block3) # Scrambler is symmetric XOR
    assert rx_block2 == block2
    
    # 4. 2D Parity Decode
    rx_block1, success = g.parity_2d_decode(rx_block2)
    assert success
    assert rx_block1 == block1
    
    # 5. Extract
    rx_payload = rx_block1[:128]
    rx_crc = rx_block1[128:]
    assert rx_payload == payload
    assert rx_crc == g.crc32(rx_payload)
    
    print("ALL TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_flow()
