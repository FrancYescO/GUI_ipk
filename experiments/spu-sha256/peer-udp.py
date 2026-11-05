"""Disposable peer NAT-T socket. Run only inside the dedicated lab container."""
import pathlib
import socket
import time
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind(('0.0.0.0', 45069))
s.settimeout(20)
s.sendto(b'SPU2PROBE', ('192.168.133.69', 45069))
message, endpoint = s.recvfrom(64)
if message != b'SPU2ACK':
    raise RuntimeError('Unexpected probe reply')
s.setsockopt(socket.IPPROTO_UDP, 100, 2)
pathlib.Path('/tmp/spu-peer-ready').write_text('READY\n')
while True:
    time.sleep(60)
