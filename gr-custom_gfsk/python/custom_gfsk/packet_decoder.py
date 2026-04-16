import numpy as np
import struct
import math
from gnuradio import gr, digital, filter, analog, fft
from . import custom_gfsk_lib as gle

STATE_SYNC_SEARCH = 0
STATE_PAYLOAD_RX = 1

class packet_decoder_logic(gr.basic_block):
    """ Internal block doing the sliding correlation and decode natively on streams. """
    def __init__(self, sync_threshold=4, enable_fec=True):
        gr.basic_block.__init__(self,
            name="Custom GFSK Packet Decoder Logic",
            in_sig=[np.uint8],
            out_sig=[np.uint8])
        
        self.enable_fec = enable_fec
        self.sync_threshold = sync_threshold
        self.sync_target = (np.array(gle.SYNC_BITS, dtype=np.int8) * 2) - 1
        self.sync_len = len(gle.SYNC_BITS)
        self.payload_bits = 1344 if enable_fec else 336
        
        self.buffer = np.array([], dtype=np.uint8)
        self.state = STATE_SYNC_SEARCH
        self.last_seq = None
        self.rx_buffer = bytearray()

    def general_work(self, input_items, output_items):
        in_buf = input_items[0]
        out_buf = output_items[0]
        
        self.buffer = np.concatenate((self.buffer, in_buf))
        self.consume(0, len(in_buf))
        
        produced = 0
        
        while True:
            # We must have enough output buffer space to export a full 38 byte payload
            if (len(out_buf) - produced) < 38:
                break
                
            if self.state == STATE_SYNC_SEARCH:
                if len(self.buffer) < self.sync_len:
                    break
                    
                buf_mapped = (self.buffer.astype(np.int8) * 2) - 1
                corr = np.correlate(buf_mapped, self.sync_target, mode='valid')
                
                min_corr = self.sync_len - 2 * self.sync_threshold
                matches = np.where(corr >= min_corr)[0]
                if len(matches) > 0:
                    match_idx = matches[0]
                    start_idx = match_idx + self.sync_len
                    self.buffer = self.buffer[start_idx:]
                    self.state = STATE_PAYLOAD_RX
                else:
                    self.buffer = self.buffer[-(self.sync_len - 1):]
                    break
                    
            elif self.state == STATE_PAYLOAD_RX:
                if len(self.buffer) < self.payload_bits:
                    break
                
                packet_bits_arr = self.buffer[:self.payload_bits]
                self.buffer = self.buffer[self.payload_bits:]
                self.state = STATE_SYNC_SEARCH
                
                packet_bytes = np.packbits(packet_bits_arr).tobytes()
                
                # Decode
                if self.enable_fec:
                    rx_block3 = gle.decode_rep3(packet_bytes)
                    rx_block2 = gle.lfsr_scramble(rx_block3)
                    rx_block1, success = gle.parity_2d_decode(rx_block2)
                else:
                    rx_block1 = gle.lfsr_scramble(packet_bytes)
                    success = True # No parity checking in Turbo Mode, strict CRC only.
                
                if success:
                    rx_payload = rx_block1[:38]
                    rx_crc = rx_block1[38:]
                    expected_crc = gle.crc32(rx_payload)
                    if rx_crc == expected_crc:
                        # Parse Protocol Header
                        seq_num = struct.unpack('>H', rx_payload[:2])[0]
                        payload_data = rx_payload[2:]
                        
                        # Detect Drops and Insert Padding
                        if self.last_seq is not None:
                            diff = (seq_num - self.last_seq) & 0xFFFF
                            if 1 < diff < 2000:
                                dropped_packets = diff - 1
                                print(f"DECODER: [!] Packet LOSS Detected! Missed {dropped_packets} frames. Injecting {dropped_packets*36} blank bytes to maintain structural alignment.")
                                self.rx_buffer.extend(b'\x00' * (36 * dropped_packets))
                                
                        self.last_seq = seq_num
                        self.rx_buffer.extend(payload_data)
                    else:
                        pass # DECODER: CRC failed.
                else:
                    pass # DECODER: 2D Parity failed.
            
            # Drain rx_buffer to out_buf securely without overflowing DSP pipeline
            remaining_space = len(out_buf) - produced
            if remaining_space > 0 and len(self.rx_buffer) > 0:
                take = min(remaining_space, len(self.rx_buffer))
                out_buf[produced:produced+take] = np.frombuffer(self.rx_buffer[:take], dtype=np.uint8)
                produced += take
                self.rx_buffer = self.rx_buffer[take:]
                        
        return produced

class packet_decoder(gr.hier_block2):
    """
    Custom GFSK RX (Hierarchical Block) - PURE STREAM MODE
    """
    def __init__(self, samples_per_symbol=2, sync_threshold=4, sample_rate=1e6, enable_fec=True):
        gr.hier_block2.__init__(self, "Custom GFSK RX",
            gr.io_signature(1, 1, gr.sizeof_gr_complex), # Complex input straight from USRP
            gr.io_signature(1, 1, gr.sizeof_char)) # Byte Stream Output
        
        # Strip Local Oscillator (LO) leakage DC offset from SDR hardware
        self.dc_blocker = filter.dc_blocker_cc(32, True)
        
        self.agc = analog.agc_cc(1e-4, 1.0, 1.0)
        self.agc.set_max_gain(65536)
        
        # 1. Dynamic Signal-Hugging Low Pass RF Filter Mathematics
        # --------------------------------------------------------
        symbol_rate = sample_rate / samples_per_symbol
        # GFSK Bandwidth is approximately the symbol rate mathematically.
        # We set the cutoff tightly at 60% of the symbol rate to lock out pure AWGN.
        optimal_cutoff = symbol_rate * 0.6 
        optimal_trans_width = symbol_rate * 0.2
        
        lpf_taps = filter.firdes.low_pass(
            1.0, sample_rate, optimal_cutoff, optimal_trans_width, fft.window.WIN_HAMMING, 6.76)
        self.lpf = filter.fir_filter_ccf(1, lpf_taps)
        
        # FLL Band-Edge Hardware Tracker (Drift Cancelation)
        self.fll = digital.fll_band_edge_cc(samples_per_symbol, 0.5, 44, 0.05)
        
        # 2. Perfect Mathematical Carrier Phase Matching
        # --------------------------------------------------------
        optimal_sensitivity = (math.pi * 0.5) / samples_per_symbol
        
        self.demodulator = digital.gfsk_demod(
            samples_per_symbol=samples_per_symbol,
            sensitivity=optimal_sensitivity, log=False, freq_error=0.0, verbose=False)
            
        self.logic = packet_decoder_logic(sync_threshold=sync_threshold, enable_fec=enable_fec)
        
        self.connect((self, 0), (self.dc_blocker, 0))
        self.connect((self.dc_blocker, 0), (self.lpf, 0))
        self.connect((self.lpf, 0), (self.fll, 0))
        self.connect((self.fll, 0), (self.agc, 0))
        self.connect((self.agc, 0), (self.demodulator, 0))
        self.connect((self.demodulator, 0), (self.logic, 0))
        self.connect((self.logic, 0), (self, 0))
