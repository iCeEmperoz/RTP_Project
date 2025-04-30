import argparse
import socket
import sys
import time
from utils import PacketHeader, compute_checksum

HEADER_SIZE = 16
MAX_PACKET_SIZE = 1472
TIME_OUT = 0.5


def sender(receiver_ip, receiver_port, window_size):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(TIME_OUT)

    message = sys.stdin.buffer.read()
    if not message:
        print("Error: No data to send.")
        s.close()
        return
        
    # Chia message thành các chunk <= payload_size
    chunk_size = MAX_PACKET_SIZE - HEADER_SIZE
    chunks = [message[i:i + chunk_size] for i in range(0, len(message), chunk_size)]
    total_chunks = len(chunks)
    receiver_addr = (receiver_ip, receiver_port)

    # START packet
    start_pkt = PacketHeader(type=0, seq_num=0, length=0, checksum=0)
    start_pkt.checksum = compute_checksum(start_pkt)
    s.sendto(bytes(start_pkt), receiver_addr)

    
    # Chờ ACK cho START 
    try:
        data, _ = s.recvfrom(MAX_PACKET_SIZE)
        ack = PacketHeader(data)
        ack_checksum = ack.checksum
        ack.checksum = 0
        if ack.type != 3 or ack.seq_num != 1 or compute_checksum(ack) != ack_checksum:
            raise Exception("Invalid START ACK")
    except:
        print("Error: Timeout or invalid ACK for START")
        s.close()
        return

    # sliding window
    base = 1         # seq_num nhỏ nhất trong window chưa được ACK
    next_seq = 1     # seq_num tiếp theo được gửi
    window = {}      # buffer lưu các gói đã gửi nhưng chưa ACK
    acked = set()    # Luu cac goi tin da nhan duoc ACK
    timer_start = time.time()

    # Gửi liên tục cho đến khi tất cả chunks được ACK
    while base <= total_chunks:
        # Gửi gói DATA vào window nếu còn slot và còn chunk
        while next_seq < base + window_size and next_seq <= total_chunks:
            payload = chunks[next_seq - 1]
            pkt = PacketHeader(type=2, seq_num=next_seq, length=len(payload), checksum=0)
            # Tính checksum cho header + payload
            pkt.checksum = compute_checksum(pkt / payload)
            full_pkt = pkt / payload
            # Gửi DATA packet
            s.sendto(bytes(full_pkt), receiver_addr)
            window[next_seq] = full_pkt
            next_seq += 1

        # Chờ ACK từ receiver
        try:
            data, _ = s.recvfrom(MAX_PACKET_SIZE)
            ack = PacketHeader(data)
            
            # Kiem tra check_sum
            cksum = ack.checksum
            ack.checksum = 0
            if compute_checksum(ack) != cksum or ack.type != 3:
                continue
            acked.add(ack.seq_num)

            while base in acked:
                del window[base]
                base += 1

            if base == next_seq:
                timer_start = time.time()
        except socket.timeout:
            if time.time() - timer_start >= TIME_OUT:
                for seq, pkt in window.items():
                    if seq not in acked:
                        s.sendto(bytes(pkt), receiver_addr)
                timer_start = time.time()

    # END packet
    end_seq = total_chunks + 1
    end_pkt = PacketHeader(type=1, seq_num=end_seq, length=0, checksum=0)
    end_pkt.checksum = compute_checksum(end_pkt)
    s.sendto(bytes(end_pkt), receiver_addr)

    start_time = time.time()
    while time.time() - start_time < TIME_OUT:
        try:
            data, _ = s.recvfrom(MAX_PACKET_SIZE)
            ack = PacketHeader(data)
            cksum = ack.checksum
            ack.checksum = 0
            # Nếu nhận được ACK hợp lệ cho END thì break
            if ack.type == 3 and ack.seq_num == end_seq + 1 and compute_checksum(ack) == cksum:
                print("Received ACK for END")
                break
        except:
            continue

    s.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("receiver_ip")
    parser.add_argument("receiver_port", type=int)
    parser.add_argument("window_size", type=int)
    args = parser.parse_args()
    sender(args.receiver_ip, args.receiver_port, args.window_size)


if __name__ == "__main__":
    main()
