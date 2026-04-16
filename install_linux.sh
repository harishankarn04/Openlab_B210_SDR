#!/bin/bash

echo "======================================================="
echo "  Openlab B210 SDR - Linux Auto-Install Script"
echo "======================================================="
echo "This script automates installing GNU Radio, UHD drivers,"
echo "and custom Python media protocols for Debian/Ubuntu."
echo "======================================================="
echo ""

echo "[1/4] Updating Apt Repositories..."
sudo apt update

echo "[2/4] Installing Hardware Drivers (GNU Radio, UHD, FFmpeg)..."
# We install native OS packages for absolute stability when interacting with SDRs
sudo apt install -y gnuradio uhd-host python3-pip ffmpeg

echo "[3/4] Installing Core Python Libraries..."
# Using APT packages for OpenCV and Numpy is highly recommended on modern Linux 
# to definitively prevent PIP/PEP-668 "Externally Managed Environment" conflicts!
sudo apt install -y python3-numpy python3-opencv python3-pil

echo "[4/4] Building and Globally Linking Core Module with CMake..."
# Installing CMake and builder tools to natively compile and place GNU Radio files into the host OS directory
sudo apt install -y cmake build-essential gnuradio-dev
cd gr-custom_gfsk
mkdir -p build && cd build
cmake ..
make
sudo make install
sudo ldconfig
cd ../..

echo ""
echo "Checking USRP Firmware Images..."
# Downloads the proprietary Ettus board firmware so the B210 can initialize
sudo uhd_images_downloader

echo ""
echo "✅ Installation Complete! Your computer is ready to radiate."
echo "Plug in your B210, configure your antennas, and type:"
echo "uhd_find_devices"
