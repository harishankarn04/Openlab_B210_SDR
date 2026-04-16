import numpy as np
import struct
import os
from PIL import Image
from gnuradio import gr

# Application Layer Constants
MAGIC_HEADER = b'\x53\x4D\x41\x52\x54\x5F\x54\x58' # "SMART_TX"
TYPE_GENERIC = 0
TYPE_JPEG = 1
TYPE_HEVC = 2
TYPE_RAW_IMAGE = 3

STATE_SEARCHING_MAGIC = 0
STATE_READING_HEADER = 1
STATE_EXTRACTING_PAYLOAD = 2

class custom_file_sink(gr.sync_block):
    """
    Custom Auto-Decompressing File Sink
    Hunts for the protocol header, extracts the exact bytes, and dumps to native file extensions.
    """
    def __init__(self, output_file=""):
        gr.sync_block.__init__(self,
            name="Custom File Sink",
            in_sig=[np.uint8],
            out_sig=None)
            
        if output_file:
            output_file = output_file.strip("\"'")
            
        self.output_file = output_file if output_file else os.path.expanduser("~/recovered_output")
        
        self.buffer = bytearray()
        self.state = STATE_SEARCHING_MAGIC
        
        self.target_size = 0
        self.target_type = 0
        self.recovered_payload = bytearray()
        
        self.last_print_len = 0

    def work(self, input_items, output_items):
        in_buf = input_items[0]
        self.buffer.extend(in_buf.tobytes())
        consumed = len(in_buf)
        
        while True:
            if self.state == STATE_SEARCHING_MAGIC:
                idx = self.buffer.find(MAGIC_HEADER)
                if idx != -1:
                    # Found Magic! Trim everything before it.
                    self.buffer = self.buffer[idx:]
                    self.state = STATE_READING_HEADER
                else:
                    # Keep the last len(MAGIC)-1 bytes in case it is split across chunks
                    keep_len = len(MAGIC_HEADER) - 1
                    self.buffer = self.buffer[-keep_len:] if len(self.buffer) > keep_len else self.buffer
                    break
                    
            elif self.state == STATE_READING_HEADER:
                header_len = len(MAGIC_HEADER) + 1 + 4
                if len(self.buffer) >= header_len:
                    # Parse the header!
                    self.target_type = self.buffer[len(MAGIC_HEADER)]
                    size_bytes = self.buffer[len(MAGIC_HEADER)+1 : header_len]
                    self.target_size = struct.unpack(">I", size_bytes)[0]
                    
                    print(f"SINK: Protocol Matched! Type: {self.target_type}, Expected Size: {self.target_size} bytes")
                    
                    self.buffer = self.buffer[header_len:]
                    self.state = STATE_EXTRACTING_PAYLOAD
                    self.recovered_payload = bytearray()
                    self.last_print_len = 0
                else:
                    break
                    
            elif self.state == STATE_EXTRACTING_PAYLOAD:
                needed = self.target_size - len(self.recovered_payload)
                if needed <= 0:
                    self.finalize_file()
                    self.state = STATE_SEARCHING_MAGIC
                    continue
                    
                take = min(needed, len(self.buffer))
                self.recovered_payload.extend(self.buffer[:take])
                self.buffer = self.buffer[take:]
                
                # Print progress bar every 50KB received of the payload
                curr_len = len(self.recovered_payload)
                if (curr_len - self.last_print_len) >= 50000:
                    progress = curr_len / self.target_size if self.target_size > 0 else 0
                    bar_len = 30
                    filled = int(bar_len * progress)
                    bar = '█' * filled + '-' * (bar_len - filled)
                    percent = progress * 100
                    import sys
                    sys.stdout.write(f"\rSINK PROGRESS:   [{bar}] {percent:.1f}% ({curr_len / 1024:.1f} KB / {self.target_size / 1024:.1f} KB)   ")
                    sys.stdout.flush()
                    self.last_print_len = curr_len
                
                if len(self.recovered_payload) == self.target_size:
                    import sys
                    sys.stdout.write(f"\rSINK PROGRESS:   [{'█' * 30}] 100.0% ({self.target_size / 1024:.1f} KB / {self.target_size / 1024:.1f} KB) ✅ DONE!\n")
                    sys.stdout.flush()
                    self.finalize_file()
                    self.state = STATE_SEARCHING_MAGIC
                else:
                    break
                    
        return consumed

    def finalize_file(self):
        ext = ".bin"
        if self.target_type == TYPE_JPEG:
            ext = ".jpg"
            print("SINK: Target acquired was an Image! Routing as .jpg")
        elif self.target_type == TYPE_HEVC:
            ext = ".mp4"
            print("SINK: Target acquired was a Video! Routing as .mp4 (HEVC)")
        elif self.target_type == TYPE_RAW_IMAGE:
            ext = ".png" # Compile Native RAW buffer to a PNG on disk for the user
            print("SINK: INDESTRUCTIBLE RAW Image payload detected!")
        
        filename = self.output_file
        if not filename.lower().endswith(ext):
            filename += ext
            
        if self.target_type == TYPE_RAW_IMAGE:
            if len(self.recovered_payload) >= 5:
                w, h, c = struct.unpack(">HHB", self.recovered_payload[:5])
                pixels = self.recovered_payload[5:]
                expected = w * h * c
                print(f"SINK: RAW Matrix specs -> {w}x{h} ({c} channels). Reconstructing resilient grid...")
                
                # Dropped packets naturally decode as zero padding. We lock it to the strict dimensions.
                if len(pixels) < expected:
                    pixels += b'\x00' * (expected - len(pixels))
                elif len(pixels) > expected:
                    pixels = pixels[:expected]
                    
                mode_str = "RGB" if c == 3 else "L"
                img = Image.frombytes(mode_str, (w, h), bytes(pixels))
                img.save(filename)
                print(f"SINK: INDESTRUCTIBLE Image safely processed regardless of packet loss -> {filename}")
            else:
                print("SINK: RAW Image completely fragmented.")
        else:
            import lzma
            print("SINK: Target acquired was a General File! Attempting LZMA Decompression...")
            try:
                dec = lzma.decompress(self.recovered_payload)
                with open(filename, 'wb') as f:
                    f.write(dec)
                print(f"SINK: File decompressed and saved to: {filename}")
            except Exception as e:
                with open(filename, 'wb') as f:
                    f.write(self.recovered_payload)
                print(f"SINK: Raw native file saved (Uncompressed/LZMA bypass) to: {filename}")
