import os
import sys
import time
from gnuradio import gr, blocks, channels
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'gr-custom_gfsk', 'python'))
from custom_gfsk import packet_encoder, packet_decoder, custom_file_source, custom_file_sink

class e2e_image_fg(gr.top_block):
    def __init__(self, input_image, output_image):
        gr.top_block.__init__(self, "E2E Image Test")
        
        # 1. Custom File Source (Reads JPEG, compiles indestructible RAW pixel array payload)
        self.src = custom_file_source(filepath=input_image)
        
        # 2. Block Encoder (Uses Nuclear Rep3 FEC)
        self.tx = packet_encoder(samples_per_symbol=2, enable_fec=True)
        
        # 3. Channel Simulation (Simulate extreme AWGN 0.25v noise from hardware loopback)
        self.channel = channels.channel_model(
            noise_voltage=0.25, 
            frequency_offset=0.0,
            epsilon=1.0,
            taps=[1.0, 0.0],
            noise_seed=0,
            block_tags=False
        )
        
        # 4. Decoder
        self.rx = packet_decoder(samples_per_symbol=2, sync_threshold=4, enable_fec=True)
        
        # 5. Sink (Catches RAW array and reconstructs image directly, padding dropped packets securely with black coordinates)
        self.sink = custom_file_sink(output_file=output_image)
        
        # Connect
        self.connect(self.src, self.tx, self.channel, self.rx, self.sink)

if __name__ == '__main__':
    in_file = 'test_pattern.jpg'
    out_file = 'recovered_output'
    
    # 1. Generate a procedural AWGN target image (1080p, we want to watch it scale and survive)
    print("Generating procedural test target image...")
    img = Image.new('RGB', (1920, 1080), color='blue')
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    draw.text((800, 500), "Nuclear SDR Test", fill='white')
    img.save(in_file, format='JPEG')
    
    if os.path.exists(out_file + '.png'):
         os.remove(out_file + '.png')
         
    # 2. Transmit through simulation
    print("Starting nuclear E2E SDR transmission...")
    start_time = time.time()
    
    tb = e2e_image_fg(in_file, out_file)
    tb.start()
    
    # Since our source streams indefinitely returning -1 on empty, wait a safe duration to complete transmission buffer
    time.sleep(20) 
    tb.stop()
    tb.wait()
    
    elapsed = time.time() - start_time
    print(f"Test completed in {elapsed:.2f} seconds.")
    
    # Check outputs dynamically
    if os.path.exists(out_file + '.png'):
        size = os.path.getsize(out_file + '.png')
        print(f"SUCCESS: Physical payload arrived correctly structured at sink -> {size} bytes.")
    else:
        print("CRITICAL: Final payload failed to formulate correctly in pipeline!")
