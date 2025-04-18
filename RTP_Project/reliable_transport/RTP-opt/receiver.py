import argparse
import socket
import sys
from utils import PacketHeader, compute_checksum

HEADER_SIZE = 16
MAX_PACKET_SIZE = 1472

def send_ack(sock, addr, seq_num):
    ack = PacketHeader(type=3, seq_num=seq_num, length=0, checksum=0)
    ack.checksum = compute_checksum(ack)
    sock.sendto(bytes(ack), addr)

def receiver(ip, port, window_size):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((ip, port))

    expected_seq = 1
    received_data = {}
    in_session = False

    while True:
        pkt_bytes, addr = sock.recvfrom(MAX_PACKET_SIZE)

        if len(pkt_bytes) < HEADER_SIZE:
            continue

        pkt = PacketHeader(pkt_bytes[:HEADER_SIZE])
        payload = pkt_bytes[HEADER_SIZE:HEADER_SIZE + pkt.length]

        original_checksum = pkt.checksum
        pkt.checksum = 0
        if compute_checksum(pkt / payload) != original_checksum:
            continue # Drop corrupted packet

        if pkt.type == 0 and pkt.seq_num == 0:
            # START packet
            in_session = True
            expected_seq = 1
            received_data.clear()
            send_ack(sock, addr, 1)

        elif pkt.type == 2 and in_session:
            # DATA packet
            if pkt.seq_num >= expected_seq + window_size:
                continue # Outside window

            if pkt.seq_num in received_data:
                send_ack(sock, addr, pkt.seq_num)
                continue

            received_data[pkt.seq_num] = payload
            send_ack(sock, addr, pkt.seq_num)

        elif pkt.type == 1 and in_session:
            # END packet
            send_ack(sock, addr, pkt.seq_num + 1)
            break

    for seq in sorted(received_data):
        sys.stdout.buffer.write(received_data[seq])
    sys.stdout.flush()
    sock.close()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("receiver_ip")
    parser.add_argument("receiver_port", type=int)
    parser.add_argument("window_size", type=int)
    args = parser.parse_args()
    receiver(args.receiver_ip, args.receiver_port, args.window_size)

if __name__ == "__main__":
    main()