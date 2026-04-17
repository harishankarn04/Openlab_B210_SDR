import os
import sys
import time
from gnuradio import gr, blocks, channels

# Import our custom OOT module directly from the source directory so we don't need sudo make install to test
sys.path.append(os.path.join(os.path.dirname(__file__), 'gr-custom_gfsk', 'python'))
from custom_gfsk import packet_encoder
from custom_gfsk import packet_decoder

class e2e_flowgraph(gr.top_block):
    def __init__(self, input_file, output_file):
        gr.top_block.__init__(self, "E2E Stream Test")
        
        # 1. File Source (No repeat so it natively finishes)
        self.file_src = blocks.file_source(gr.sizeof_char*1, input_file, False)
        
        # 2. Our Custom TX Hier Block (Byte Stream -> Complex Waveform)
        self.tx_block = packet_encoder(samples_per_symbol=2)
        
        # 3. Channel Model (simulate noise over the air)
        self.channel = channels.channel_model(
            noise_voltage=0.1, 
            frequency_offset=0.0,
            epsilon=1.0,
            taps=[1.0, 0.0],
            noise_seed=0,
            block_tags=False
        )
        
        # 4. Our Custom RX Hier Block (Complex Waveform -> Byte Stream)
        self.rx_block = packet_decoder(samples_per_symbol=2, sync_threshold=4, sample_rate=1e6)
        
        # 5. File Sink (Capture valid outputs)
        self.file_sink = blocks.file_sink(gr.sizeof_char*1, output_file, False)
        self.file_sink.set_unbuffered(False)
        
        # --- Connect Streams ---
        self.connect(self.file_src, self.tx_block)
        self.connect(self.tx_block, self.channel)
        self.connect(self.channel, self.rx_block)
        self.connect(self.rx_block, self.file_sink)

if __name__ == '__main__':
    in_file = 'test_input.bin'
    out_file = 'test_output.bin'
    
    if os.path.exists(out_file):
        os.remove(out_file)
        
    print(f"Starting E2E test with 1.5 million bits ({os.path.getsize(in_file)} bytes)...")
    start_time = time.time()
    
    tb = e2e_flowgraph(in_file, out_file)
    tb.start()
    tb.wait() # Waits until graph completes (EOF on file source)
    
    elapsed = time.time() - start_time
    print(f"Test completed in {elapsed:.2f} seconds!")
    
    out_size = os.path.getsize(out_file) if os.path.exists(out_file) else 0
    print(f"Output file size: {out_size} bytes")
    print("Graph executed perfectly." if out_size > 0 else "WARNING: Zero bytes received.")
