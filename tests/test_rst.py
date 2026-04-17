import cv2
import numpy as np
import os

# Create dummy image
img = np.zeros((400, 400, 3), dtype=np.uint8)
cv2.rectangle(img, (100, 100), (300, 300), (255, 0, 0), -1)

# Encode without RST
ret, buf_normal = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 75])
buf_normal = bytearray(buf_normal)

# Encode with RST
ret, buf_rst = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 75, cv2.IMWRITE_JPEG_RST_INTERVAL, 1])
buf_rst = bytearray(buf_rst)

print(f"Normal Size: {len(buf_normal)} bytes")
print(f"RST Size: {len(buf_rst)} bytes")

# Corrupt both by overwriting 200 bytes in the middle with zeros (mimicking dropped packet padding)
drop_idx = len(buf_normal) // 2
buf_normal[drop_idx:drop_idx+200] = b'\x00' * 200

drop_idx2 = len(buf_rst) // 2
buf_rst[drop_idx2:drop_idx2+200] = b'\x00' * 200

with open('out_normal.jpg', 'wb') as f:
    f.write(buf_normal)
    
with open('out_rst.jpg', 'wb') as f:
    f.write(buf_rst)

print("Saved corrupted JPEGs. Check if RST version survived the structure!")
