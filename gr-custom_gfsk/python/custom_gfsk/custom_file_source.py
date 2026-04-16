import os
import subprocess
import tempfile
import struct
import numpy as np
import threading
import time
from PIL import Image, ImageStat
from gnuradio import gr

# Application Layer Constants
MAGIC_HEADER = b'\x53\x4D\x41\x52\x54\x5F\x54\x58' # "SMART_TX"
TYPE_GENERIC = 0
TYPE_JPEG = 1
TYPE_HEVC = 2
TYPE_RAW_IMAGE = 3

class custom_file_source(gr.sync_block):
    """
    Custom Auto-Compressing File Source
    Reads a file, compresses to JPEG/HEVC, adds header, and outputs byte stream.
    """
    def __init__(self, filepath="", image_quality=30, video_resolution=480, video_fps=24, video_bitrate=200):
        gr.sync_block.__init__(self,
            name="Custom File Source",
            in_sig=None,
            out_sig=[np.uint8])
            
        self.payload = bytearray()
        self.idx = 0
        
        # Safely strip any nested strings injected by GRC file_open widgets
        if filepath:
            filepath = filepath.strip("\"'")
            
        self.image_quality = max(1, min(100, int(image_quality)))
        self.video_resolution = max(144, min(1080, int(video_resolution)))
        self.video_fps = max(1, min(60, int(video_fps)))
        self.video_bitrate = max(10, int(video_bitrate))
        self.last_print_idx = 0
        self.ready_to_transmit = False
        self.flowgraph_finished = False
        
        print(f"\n[+] SOURCE INIT: Starting Custom File Source Block!")
        print(f"[-] Targeting File: '{filepath}'")
        
        if filepath and os.path.exists(filepath):
            # Spawn Background Thread to prevent GNURadio UI Freezing
            t = threading.Thread(target=self.prepare_payload, args=(filepath,))
            t.daemon = True
            t.start()
        else:
            print("ERROR: Filepath is empty or does not exist on disk!")
            raise ValueError(f"Custom File Source cannot open file: {filepath}")
            
    def prepare_payload(self, filepath):
        ext = filepath.lower().split('.')[-1]
        
        file_type = TYPE_GENERIC
        final_data = b""
        
        if ext in ['jpg', 'jpeg', 'png', 'bmp']:
            print(f"SOURCE: Detected Image. Structuring into INDESTRUCTIBLE JPEG (Restart Interval)...")
            file_type = TYPE_JPEG
            try:
                # We revert back to compression to save aggressive bandwidth, but use 'Restart Markers'
                # to physically ensure horizontal desync tearing cannot spread across blocks!!
                import cv2
                img_np = cv2.imread(filepath)
                if img_np is None:
                    raise ValueError("OpenCV could not parse the image matrix.")
                
                # cv2.IMWRITE_JPEG_QUALITY (1), self.image_quality (75)
                # cv2.IMWRITE_JPEG_RST_INTERVAL (4), 1 (Insert marker every MCU block!)
                ret, buf = cv2.imencode('.jpg', img_np, [1, self.image_quality, 4, 1])
                if not ret:
                    raise ValueError("OpenCV failed to bind Restart markers.")
                    
                final_data = buf.tobytes()
                print(f"SOURCE: Compressed into resilient JPEG structure. Final Size: {len(final_data)} bytes")
            except Exception as e:
                print(f"SOURCE: JPEG RST encoding structurally failed ({e}). Falling back to RAW binary stream.")
                with open(filepath, 'rb') as f:
                    final_data = f.read()
                    
        elif ext in ['mp4', 'avi', 'mkv', 'mov']:
            print(f"SOURCE: Detected Video. Transcoding to HEVC (H.265)...")
            file_type = TYPE_HEVC
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp:
                tmp_name = tmp.name
                
            cmd = [
                'ffmpeg', '-y', '-i', filepath,
                '-vf', f'scale=-2:{self.video_resolution}', # User-Defined Transcode Resolution
                '-r', str(self.video_fps),                  # User-Defined Framerate
                '-c:v', 'libx265', '-crf', '32', '-preset', 'faster', # Balanced HEVC Compression
                '-c:a', 'aac', '-b:v', f'{self.video_bitrate}k', '-b:a', '32k', '-ac', '2', # 32k Stereo Audio
                tmp_name
            ]
            try:
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                with open(tmp_name, 'rb') as f:
                    final_data = f.read()
                print(f"SOURCE: Video transcoded to HEVC via ffmpeg. Size: {len(final_data)} bytes")
            except Exception as e:
                print(f"SOURCE: Failed to transcode video ({e}). Falling back to raw.")
                with open(filepath, 'rb') as f:
                    final_data = f.read()
            finally:
                if os.path.exists(tmp_name):
                    os.remove(tmp_name)
        else:
            import lzma
            print(f"SOURCE: Generic file format detected. Emulating original behavior by compressing with LZMA natively...")
            try:
                with open(filepath, 'rb') as f:
                    raw = f.read()
                final_data = lzma.compress(raw)
                print(f"SOURCE: LZMA Compression complete! Size: {len(final_data)} bytes")
            except Exception as e:
                print(f"SOURCE: LZMA compression failed ({e}). Embedding natively.")
                with open(filepath, 'rb') as f:
                    final_data = f.read()
                
        # Build Protocol Header
        length_bytes = struct.pack(">I", len(final_data))
        header = MAGIC_HEADER + bytes([file_type]) + length_bytes
        # Formulate hardware safety margin. USRP USB queues aggressively buffer and overflow instantly on startup!
        # Transmitting 50 KB of empty data physically buys the receiver AGC and FLL 1.5 seconds to perfectly lock.
        warmup_padding = b'\x00' * 50000 
        
        self.payload = bytearray(warmup_padding + header + final_data)
        
        # Add End-of-Transmission (EOT) Padding to flush USRP FIR filters!
        self.payload.extend(b'\x00' * 5000)
        self.ready_to_transmit = True
        print(f"SOURCE: Compression Finished! Full Buffer Ready to Trasmitt. Total Size: {len(self.payload)} bytes.")

    def work(self, input_items, output_items):
        if not self.ready_to_transmit:
            # Yield CPU natively so GNU Radio doesn't detect a freeze
            time.sleep(0.01)
            return 0
            
        out = output_items[0]
        
        if self.idx >= len(self.payload):
            if not self.flowgraph_finished:
                import sys
                sys.stdout.write(f"\rSOURCE PROGRESS: [{'█' * 30}] 100.0% ({len(self.payload) / 1024:.1f} KB / {len(self.payload) / 1024:.1f} KB) ✅ DONE!\n")
                sys.stdout.flush()
                print("SOURCE: Transmission Complete! Shutting down stream.")
                self.flowgraph_finished = True
            return -1
            
        remaining = len(self.payload) - self.idx
        to_write = min(len(out), remaining)
        
        out[:to_write] = np.frombuffer(self.payload[self.idx : self.idx+to_write], dtype=np.uint8)
        self.idx += to_write
        
        # Print progress bar every 50KB
        if (self.idx - self.last_print_idx) >= 50000:
            progress = self.idx / len(self.payload) if len(self.payload) > 0 else 0
            bar_len = 30
            filled = int(bar_len * progress)
            bar = '█' * filled + '-' * (bar_len - filled)
            percent = progress * 100
            import sys
            sys.stdout.write(f"\rSOURCE PROGRESS: [{bar}] {percent:.1f}% ({self.idx / 1024:.1f} KB / {len(self.payload) / 1024:.1f} KB)   ")
            sys.stdout.flush()
            self.last_print_idx = self.idx
            
        return to_write
