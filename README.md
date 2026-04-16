# Openlab B210 SDR (Robust Custom GFSK)

A comprehensive, formally structured GNU Radio Out-Of-Tree (OOT) module designed to provide a virtually indestructible Custom GFSK transceiver system for Ettus USRP B210 hardware. 

This repository leverages an extreme "Nuclear" Forward Error Correction (FEC) mechanism paired natively with a Smart Application Layer that dynamically compresses, transmits, and physically re-assembles images and video across over-the-air (OTA) RF channels.

## Core Features
* **Triple Redundant (REP3) FEC:** Mathematically tolerates up to 33% bit corruption using majority-voting algorithms.
* **Smart Media Sink/Source:** Natively drops in standard GNU Radio file sinks/sources.
   * **Images:** Automatically structures OpenCV `cv2` JPEGs using resilient Restart Markers to physically constrain tearing across the image during packet loss.
   * **Video:** Spawns `ffmpeg` transcoding on the fly to aggressively compress video to HEVC (H.265) down to 200kbps before transmission.
* **In-Line Native UI:** Outputs clean, single-line console loading bars (`[████------] 30%`) in the terminal.

## Setup & Installation (Linux/Debian)

To quickly deploy this SDR module onto a fresh Linux machine (e.g. Ubuntu):

1. **Clone the repository:**
   ```bash
   git clone https://github.com/harishankarn04/Openlab_B210_SDR.git
   cd Openlab_B210_SDR
   ```

2. **Run the Automated Installer:**
   There is a dedicated script that automatically interacts with `apt` to securely install all system dependencies (GNU Radio, UHD Drivers, FFmpeg) and Python packages while overriding PEP-668 bottlenecks cleanly:
   ```bash
   chmod +x install_linux.sh
   sudo ./install_linux.sh
   ```

3. **Verify Radio Connectivity:**
   Plug in your USRP B210 into a USB 3.0 port and run:
   ```bash
   uhd_find_devices
   ```

## Running the Radio

1. Compile and execute the software by opening GNU Radio Companion:
   ```bash
   gnuradio-companion hardware_test.grc
   ```
2. By default, the `hardware_test.grc` is mapped perfectly to a single USRP B210 (`RX2`/`TX_RX` ports). Connect Vivaldi Antennas and execute!
3. If you do not have hardware plugged in, you can validate the code purely in math using `gnuradio-companion simulation_test.grc`.

> **⚠️ WARNING:** Do not connect the TX and RX ports directly with an SMA cable without placing a physical inline attenuator (minimum 30dB) in the loop! Running loopbacks with 50+ dB of `tx_gain` on a naked SMA cable will permanently destroy the low-noise amplifier on the B210. 

## Running Unit Tests (No SDR Required)

If you want to rapidly test the protocol's mathematical integrity (like benchmarking the `encode_rep3` corruption threshold) without physically transmitting or opening GNU Radio, you can run the localized Root Python Tests. 

These perform instantaneous End-to-End (`e2e`) virtual testing dynamically bridging the codebase in your terminal:
```bash
python3 e2e_image_test.py
python3 test_fec.py
```
**(This folder also includes `e2e_test.py` and `test_lib.py` for raw benchmarking).*

## Making Code Changes (For Developers)

If you need to modify the protocol's logic (such as adjusting the `encode_rep3` Nuclear FEC equations or configuring OpenCV compression limits):

1. Open a code editor and modify the raw Python files located explicitly inside: `Openlab_B210_SDR/gr-custom_gfsk/python/custom_gfsk/`
2. To dynamically push your new code back to GNU Radio, enter your compilation folder and trigger the install map:
   ```bash
   cd Openlab_B210_SDR/gr-custom_gfsk/build
   sudo make install
   ```
3. Your new transmission logic will be instantly active the next time you hit Play in GNU Radio Companion!
