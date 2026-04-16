import numpy as np
import struct
import math
from gnuradio import gr, digital, blocks
from . import custom_gfsk_lib as gle

class packet_encoder_logic(gr.basic_block):
    """ Internal block doing the actual packet processing on Streams. """
    def __init__(self, enable_fec=True):
        gr.basic_block.__init__(self,
            name="Custom GFSK Packet Encoder Logic",
            in_sig=[np.uint8],
            out_sig=[np.uint8])
            
        self.enable_fec = enable_fec
        self.chunk_size = 36 # Reduced from 38 to fit a 2-byte sequence header (36 + 2 = 38 payload)
        self.out_size = 184 if enable_fec else 58
        self.seq_num = 0

    def general_work(self, input_items, output_items):
        in_buf = input_items[0]
        out_buf = output_items[0]
        
        # We need at least full 38 bytes input, and exactly 128 bytes output space
        if len(in_buf) < self.chunk_size or len(out_buf) < self.out_size:
            return 0
            
        produced = 0
        consumed = 0
        
        # 0. Hardware Phase-Lock Training Sequence
        # Blast exactly 50,000 bytes of PURE 0x55 (10101010) over the airwaves immediately on startup.
        # This completely bypasses the Scrambler and Protocol Logic, feeding the physical USRP FLL and AGC 
        # a pristine contiguous oscillating tone to violently lock its tracking loops before data arrives!
        if getattr(self, 'training_bytes_sent', 0) < 50000:
            while getattr(self, 'training_bytes_sent', 0) < 50000 and (len(out_buf) - produced) > 0:
                take = min(50000 - getattr(self, 'training_bytes_sent', 0), len(out_buf) - produced)
                out_buf[produced:produced+take] = 0x55
                self.training_bytes_sent = getattr(self, 'training_bytes_sent', 0) + take
                produced += take
            if self.training_bytes_sent < 50000:
                self.consume(0, consumed)
                return produced
        
        while (len(in_buf) - consumed) >= self.chunk_size and (len(out_buf) - produced) >= self.out_size:
            raw_data = in_buf[consumed:consumed+self.chunk_size].tobytes()
            consumed += self.chunk_size
            
            # 1. Prepend Sequence Number
            seq_bytes = struct.pack('>H', self.seq_num)
            payload_bytes = seq_bytes + raw_data
            self.seq_num = (self.seq_num + 1) & 0xFFFF
            
            # 2. Append CRC32
            crc = gle.crc32(payload_bytes)
            block1 = payload_bytes + crc
            
            if self.enable_fec:
                # 3. Apply 2D Parity
                block2 = gle.parity_2d_encode(block1)
                
                # 4. Scramble
                block3 = gle.lfsr_scramble(block2)
                
                # 5. Triple-Redundancy Geometry Expansion
                block5 = gle.encode_rep3(block3)
            else:
                block5 = gle.lfsr_scramble(block1)
            
            # 7. Prepend Preamble and Sync
            final_frame = gle.PREAMBLE + gle.SYNC_WORD + block5
            
            # Output
            out_buf[produced:produced+self.out_size] = np.frombuffer(final_frame, dtype=np.uint8)
            produced += self.out_size
            
        self.consume(0, consumed)
        return produced

class packet_encoder(gr.hier_block2):
    """
    Custom GFSK TX (Hierarchical Block) - PURE STREAM MODE
    """
    def __init__(self, samples_per_symbol=2, tx_amplitude=0.7, enable_fec=True):
        gr.hier_block2.__init__(self, "Custom GFSK TX",
            gr.io_signature(1, 1, gr.sizeof_char), # Byte Stream Input
            gr.io_signature(1, 1, gr.sizeof_gr_complex)) # outputs complex baseband

        self.logic = packet_encoder_logic(enable_fec=enable_fec)
        
        # Absolute mathematics for perfect spectral shaping based on SPS
        optimal_sensitivity = (math.pi * 0.5) / samples_per_symbol
        
        self.modulator = digital.gfsk_mod(
            samples_per_symbol=samples_per_symbol,
            sensitivity=optimal_sensitivity,
            bt=0.5, # Wide ISI tolerance setting for deep AWGN static
            verbose=False,
            log=False
        )
        
        # Scale to prevent physical B210 DAC clipping interpolation artifacts
        self.amp_scalar = blocks.multiply_const_cc(tx_amplitude)
        
        self.connect((self, 0), (self.logic, 0))
        self.connect((self.logic, 0), (self.modulator, 0))
        self.connect((self.modulator, 0), (self.amp_scalar, 0))
        self.connect((self.amp_scalar, 0), (self, 0))
