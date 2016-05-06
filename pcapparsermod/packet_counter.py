from __future__ import unicode_literals, print_function, division

_packet_counter = 0

def inc():
    global _packet_counter
    _packet_counter += 1
    
def get():
    return _packet_counter