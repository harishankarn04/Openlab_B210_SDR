#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: Smart GFSK Test
# Description: Smart GFSK Loopback with Custom Media Source/Sink
# GNU Radio version: 3.10.12.0

from custom_gfsk import custom_file_sink
from custom_gfsk import custom_file_source
from custom_gfsk import packet_decoder
from custom_gfsk import packet_encoder
from gnuradio import channels
from gnuradio.filter import firdes
from gnuradio import gr
from gnuradio.fft import window
import sys
import signal
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import eng_notation
import threading




class simulation_test(gr.top_block):

    def __init__(self):
        gr.top_block.__init__(self, "Smart GFSK Test", catch_exceptions=True)
        self.flowgraph_started = threading.Event()

        ##################################################
        # Variables
        ##################################################
        self.samp_rate = samp_rate = 1000000

        ##################################################
        # Blocks
        ##################################################

        self.custom_gfsk_tx_0 = packet_encoder(samples_per_symbol=2, tx_amplitude=0.7, enable_fec=True)
        self.custom_gfsk_rx_0 = packet_decoder(samples_per_symbol=2, sync_threshold=4, sample_rate=samp_rate, enable_fec=True)
        self.custom_gfsk_custom_file_source_0 = custom_file_source(filepath='/Users/harishankar/Documents/gitClone/SDR_USPR_B210/images/shadab.jpeg', image_quality=30, video_resolution=480, video_fps=24, video_bitrate=200)
        self.custom_gfsk_custom_file_sink_0 = custom_file_sink(output_file='/Users/harishankar/Documents/gitClone/SDR_USPR_B210/images/shadab_output.jpg')
        self.channels_channel_model_0 = channels.channel_model(
            noise_voltage=0.1,
            frequency_offset=0.0,
            epsilon=1.0,
            taps=[1.0],
            noise_seed=0,
            block_tags=False)


        ##################################################
        # Connections
        ##################################################
        self.connect((self.channels_channel_model_0, 0), (self.custom_gfsk_rx_0, 0))
        self.connect((self.custom_gfsk_custom_file_source_0, 0), (self.custom_gfsk_tx_0, 0))
        self.connect((self.custom_gfsk_rx_0, 0), (self.custom_gfsk_custom_file_sink_0, 0))
        self.connect((self.custom_gfsk_tx_0, 0), (self.channels_channel_model_0, 0))


    def get_samp_rate(self):
        return self.samp_rate

    def set_samp_rate(self, samp_rate):
        self.samp_rate = samp_rate




def main(top_block_cls=simulation_test, options=None):
    tb = top_block_cls()

    def sig_handler(sig=None, frame=None):
        tb.stop()
        tb.wait()

        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    tb.start()
    tb.flowgraph_started.set()

    try:
        input('Press Enter to quit: ')
    except EOFError:
        pass
    tb.stop()
    tb.wait()


if __name__ == '__main__':
    main()
