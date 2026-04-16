# Project Context: Custom GFSK Transceiver with FEC

## Overview
This project is a custom GNU Radio Out-Of-Tree (OOT) implementation of a robust GFSK (Gaussian Frequency Shift Keying) transceiver system. It is built using Python-based hierarchical blocks (`gr.hier_block2`). The main feature is an indestructible custom protocol stack with comprehensive "Nuclear" Forward Error Correction (FEC) and sequence-numbered packet tracking designed to ensure highly reliable image, video, and data delivery over noisy RF channels.

## Core Protocol Flow
The protocol natively chunks data into 128-byte segments and applies a heavy-duty pipeline:
1. **Padding & Sequence Tracking**: Pads payloads and injects sequence numbers to calculate automated packet-loss recovery.
2. **CRC32**: Appends a 4-byte CRC.
3. **2D Parity**: Applies 2D parity encoding robust enough to correct byte errors.
4. **Scrambling**: Scrambles data using an LFSR to prevent long runs of 1s or 0s.
5. **Nuclear REP3 Redundancy**: An extreme payload redundancy algorithm (`encode_rep3`) that literally duplicates the payload 3 times. On the RX side, it uses a bitwise majority-voting algorithm to perfectly reconstruct data even if 33% of the bits are violently corrupted out of the air.
6. **Framing**: Prepends a standard Preamble (16 bytes) and a 64-bit Sync Word optimized for SDR sliding correlation.

## Key Files & Structure (Natively Installed via Conda)
The entire project has been cleaned up and securely installed deep within the `openlab` Conda environment's `site-packages` as a formal GNU Radio Module. The remaining source code resides in:
* **`gr-custom_gfsk/`**: The formal GNU Radio Out-Of-Tree (OOT) codebase containing the `python/` and `grc/` blocks.
  * **`custom_gfsk_lib.py`**: The mathematical and bit-manipulation engine containing the Nuclear REP3 and fast LUT-based encoding.
  * **`packet_encoder.py` & `packet_decoder.py`**: The GNU Radio Complex Baseband logic (GFSK Mod/Demod, AGC, FLL Band-edge).

### Advanced Application Layer (Smart Media Blocks)
* **`custom_file_source.py` & `custom_file_sink.py`**: Smart Sink/Source blocks for GNU Radio. They detect file types (images, videos, generic) and apply smart compression automatically:
  * **Images**: Compressed natively via OpenCV (`cv2`) into highly resilient JPEG structures using 'Restart Markers'. If a few packets drop during an RF transmission, Restart Markers prevent horizontal tearing across the image and restrict the damage to a small static gray block.
  * **Video**: On-the-fly transcoding to HEVC (H.265) using `ffmpeg` to minimize RF bandwidth (e.g. shrinking 50MB to a few KB).
  * **Generic Data**: Natively compressed using `lzma`.
* **Terminal UI**: These blocks natively render rigid Console loading bars (`[████------] 30%`) using standard terminal carriage returns (`\r`) so progress tracking is clean and strictly ticks down rather than spamming the GNU Radio logs.

### Testing and Validation Flowgraphs
* **`e2e_test.py` & `e2e_image_test.py`**: Terminal-based isolated testing scripts.
* **`simulation_test_smart.grc`**: The primary software-defined GRC simulation flowgraph using the AWGN Channel Model.
* **`hardware_test.grc`**: A flowgraph explicitly built for testing over-the-air with actual physical SDR hardware (USRP B210).

## Current Project Phase
The workspace root has been wiped clean of legacy files, redundant Python units, and dummy text files. The current phase is focused strictly on implementing physical **Hardware Support using the Ettus USRP B210**, phasing out the virtual AWGN simulations to test real RF airgapped communications.

## Cross-Platform Linux Deployment Architecture
For deployment outside of the macOS/Conda sandbox, this project includes native Linux synchronization protocols:
* **`install_linux.sh`**: A highly robust automation bash script that leverages `.deb`/`apt` native frameworks to automatically download `gnuradio`, `uhd-host`, `ffmpeg`, and standard Python requirements. It safely sidesteps modern PIP PEP-668 "Externally Managed Environment" errors by utilizing pure APT distributions of Python's OpenCV. The script completely containerizes the OOT deployment locally.
* **`requirements.txt`**: Standard fallback definitions indicating hard dependencies (`numpy >= 1.20`, `opencv-python >= 4.5`, `Pillow >= 8.0`).
* **`README.md`**: Provides standardized, user-facing documentation detailing setup schemas and explicit hardware loopback warnings (attenuation requirements for SMA testing). Future chatbots should consult the README natively.
* **Recompiling Changes**: If a future chatbot or developer modifies any Python file inside `gr-custom_gfsk/python/custom_gfsk/`, they must navigate to the natively generated `gr-custom_gfsk/build/` directory and execute `sudo make install` to successfully dynamically relink the Python modifications into the host OS GNU Radio engine!
