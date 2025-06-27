import socket
import time
import struct
import random


class UDPServer:
    def __init__(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.buffer = {}  # 存储已接收但未按序排列的数据包
        self.expected_seq = 1  # 期望接收的下一个序列号
        self.loss_rate = 0.2  # 丢包率20%
        self.server_address = None

    def start(self):
        # 获取服务器IP地址
        server_ip = input("请输入服务器IP地址: ")
        server_port = int(input("请输入服务器端口号: "))
        self.server_address = (server_ip, server_port)

        # 绑定套接字
        self.server_socket.bind(self.server_address)
        print(f"服务器已启动，监听地址: {server_ip}:{server_port}")

        # 模拟TCP连接建立
        self._handle_connection_establishment()

        # 接收数据
        try:
            while True:
                data, client_address = self.server_socket.recvfrom(1024)
                packet = self._parse_packet(data)

                # 处理FIN包
                if packet['fin']:
                    self._handle_connection_closure(client_address, packet)
                    break

                # 模拟丢包
                if random.random() < self.loss_rate:
                    print(f"模拟丢包: 第{packet['seq']}个数据包")
                    continue

                # 处理数据包
                self._handle_packet(client_address, packet)

        except KeyboardInterrupt:
            print("\n程序被用户中断")
        finally:
            self.server_socket.close()

    def _handle_connection_establishment(self):
        # 模拟TCP的三次握手
        # 1. 接收客户端的SYN包
        while True:
            data, client_address = self.server_socket.recvfrom(1024)
            packet = self._parse_packet(data)
            if packet['syn']:
                break

        # 2. 发送SYN+ACK包
        syn_ack_packet = self._create_packet(seq=1, ack=packet['seq'] + 1, syn=1, fin=0, data=b'')
        self.server_socket.sendto(syn_ack_packet, client_address)

        # 3. 接收客户端的ACK包
        while True:
            try:
                self.server_socket.settimeout(1.0)
                data, client_address = self.server_socket.recvfrom(1024)
                packet = self._parse_packet(data)
                if packet['ack']:
                    break
            except socket.timeout:
                # 超时重传SYN+ACK
                self.server_socket.sendto(syn_ack_packet, client_address)

        print("连接已建立")

    def _handle_connection_closure(self, client_address, packet):
        # 模拟TCP的四次挥手
        # 发送ACK
        ack_packet = self._create_packet(seq=packet['ack'], ack=packet['seq'] + 1, syn=0, fin=0, data=b'')
        self.server_socket.sendto(ack_packet, client_address)

        # 发送FIN
        fin_packet = self._create_packet(seq=packet['ack'] + 1, ack=packet['seq'] + 1, syn=0, fin=1, data=b'')
        self.server_socket.sendto(fin_packet, client_address)

        # 接收ACK
        while True:
            try:
                self.server_socket.settimeout(1.0)
                data, _ = self.server_socket.recvfrom(1024)
                packet = self._parse_packet(data)
                if packet['ack']:
                    break
            except socket.timeout:
                # 超时重传FIN
                self.server_socket.sendto(fin_packet, client_address)

        print("连接已关闭")

    def _handle_packet(self, client_address, packet):
        seq_num = packet['seq']

        # 情况1：收到期望的或之前的包（可能是重传）
        if seq_num <= self.expected_seq:
            # 存储数据包
            self.buffer[seq_num] = packet

            # 按序交付：从expected_seq开始连续交付
            while self.expected_seq in self.buffer:
                # 处理数据（这里只是打印）
                start_byte = (self.expected_seq - 1) * 80 + 1
                end_byte = self.expected_seq * 80
                print(f"已接收第{self.expected_seq}个（第{start_byte}-{end_byte}字节）数据包")
                del self.buffer[self.expected_seq]
                self.expected_seq += 1

            # 发送累计确认
            ack_packet = self._create_packet(
                seq=packet['ack'],
                ack=self.expected_seq - 1,
                syn=0,
                fin=0,
                data=b''
            )
            self.server_socket.sendto(ack_packet, client_address)
        else:
            # 收到了一个超前的数据包，缓存它
            self.buffer[seq_num] = packet

            # 发送当前的ACK
            ack_packet = self._create_packet(
                seq=packet['ack'],
                ack=self.expected_seq - 1,
                syn=0,
                fin=0,
                data=b''
            )
            self.server_socket.sendto(ack_packet, client_address)

    def _create_packet(self, seq, ack, syn, fin, data):
        # 自定义协议首部格式
        # 4字节序列号 + 4字节确认号 + 1字节标志位 + 4字节时间戳 + 数据
        flags = (syn << 1) | fin
        timestamp = int(time.time())
        header = struct.pack('!IIBI', seq, ack, flags, timestamp)
        return header + data

    def _parse_packet(self, packet_data):
        # 解析数据包
        header = packet_data[:13]
        seq, ack, flags, timestamp = struct.unpack('!IIBI', header)
        syn = (flags & 0x02) >> 1
        fin = flags & 0x01
        return {
            'seq': seq,
            'ack': ack,
            'syn': syn,
            'fin': fin,
            'timestamp': timestamp,
            'data': packet_data[13:]
        }


if __name__ == "__main__":
    server = UDPServer()
    server.start()