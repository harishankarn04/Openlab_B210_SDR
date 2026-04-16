from PIL import Image

try:
    img1 = Image.open('out_normal.jpg')
    img1.load()
    print("Normal JPEG: Loaded fine?")
except Exception as e:
    print(f"Normal JPEG Crash: {e}")
    
try:
    img2 = Image.open('out_rst.jpg')
    img2.load()
    print("RST JPEG: Loaded fine!")
except Exception as e:
    print(f"RST JPEG Crash: {e}")
