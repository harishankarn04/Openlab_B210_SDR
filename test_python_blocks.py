import numpy as np
from packet_encoder import packet_encoder
from packet_decoder import packet_decoder
import pmt
import custom_gfsk_lib as gle

class DummyMsgPort:
    def __init__(self):
        self.published = []
    def message_port_pub(self, port, msg):
        print("PUBLISHED PDU!")
        self.published.append(msg)

def test():
    # 1. Encode
    enc = packet_encoder()
    # mock pub
    dummy = DummyMsgPort()
    enc.message_port_pub = dummy.message_port_pub
    
    msg = pmt.cons(pmt.make_dict(), pmt.init_u8vector(128, list(b"A"*128)))
    enc.handle_msg(msg)
    
    out_msg = dummy.published[0]
    encoded_bytes = bytes(pmt.u8vector_elements(pmt.cdr(out_msg)))
    print("Encoded bytes length:", len(encoded_bytes))
    
    # Simulate GFSK unpacked unpackbits (perfect channel)
    unpacked_bits = np.unpackbits(np.frombuffer(encoded_bytes, dtype=np.uint8))
    
    # 2. Decode
    dec = packet_decoder(sync_threshold=4)
    dec.message_port_pub = dummy.message_port_pub
    
    # Feed chunks
    dec.work([unpacked_bits], None)
    
if __name__ == '__main__':
    test()
