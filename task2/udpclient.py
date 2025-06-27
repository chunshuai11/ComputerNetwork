import socket
import time
import struct

import pandas as pd


class UDPClient:
    def __init__(self):
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.client_socket.settimeout(0.3)  # 设置超时时间为300ms
        self.base = 1
        self.next_seq = 1
        self.buffer_size = 5
        self.window = {}  # 存储已发送但未确认的数据包
        self.rtt_data = []  # 存储RTT数据
        self.total_packets = 30  # 总共要发送的数据包数量
        self.total_attempts = 0  # 总尝试次数
        self.lost_packets = 0  # 丢包数
        self.server_address = None

    def start(self):
        # 获取服务器地址和端口
        server_ip = input("请输入服务器IP地址: ")
        server_port = int(input("请输入服务器端口号: "))
        self.server_address = (server_ip, server_port)

        # 模拟TCP连接建立
        self._establish_connection()

        # 发送数据
        try:
            while self.base <= self.total_packets:
                # 发送窗口内的数据包最多5个
                while self.next_seq < self.base + self.buffer_size and self.next_seq <= self.total_packets:
                    self._send_packet(self.next_seq)
                    self.next_seq += 1

                # 等待确认
                try:
                    data, addr = self.client_socket.recvfrom(1024)
                    #提取头部信息
                    ack_packet = self._parse_packet(data)
                    if ack_packet['ack'] >= self.base:
                        # 计算RTT
                        seq_acknowledged = ack_packet['ack']
                        if seq_acknowledged in self.window:
                            send_time = self.window[seq_acknowledged]['send_time']
                            rtt = (time.time() - send_time) * 1000  # 转换为毫秒
                            self.rtt_data.append(rtt)

                            # 打印确认信息
                            start_byte = (seq_acknowledged - 1) * 80 + 1
                            end_byte = seq_acknowledged * 80
                            print(
                                f"第{seq_acknowledged}个（第{start_byte}-{end_byte}字节），server端已经收到，RTT是 {rtt:.2f} ms")

                            # 移除已确认的数据包
                            for seq in list(self.window.keys()):
                                if seq <= seq_acknowledged:
                                    del self.window[seq]

                            # 滑动窗口
                            self.base = seq_acknowledged + 1
                except socket.timeout:
                    # 超时重传
                    seq_to_retransmit = self.base
                    if seq_to_retransmit in self.window:
                        self._send_packet(seq_to_retransmit, is_retransmit=True)

        except KeyboardInterrupt:
            print("\n程序被用户中断")
        finally:
            # 关闭连接
            self._close_connection()
            # 打印汇总信息
            self._print_summary()
            self.client_socket.close()

    def _establish_connection(self):
        # 模拟TCP的三次握手
        # 1. 发送SYN包
        syn_packet = self._create_packet(seq=0, ack=0, syn=1, fin=0, data=b'')
        self.client_socket.sendto(syn_packet, self.server_address)

        # 2. 等待SYN+ACK包
        while True:
            try:
                data, addr = self.client_socket.recvfrom(1024)
                packet = self._parse_packet(data)
                if packet['syn'] and packet['ack']:
                    break
            except socket.timeout:
                # 超时重传SYN
                self.client_socket.sendto(syn_packet, self.server_address)

        # 3. 发送ACK包
        ack_packet = self._create_packet(seq=1, ack=1, syn=0, fin=0, data=b'')
        self.client_socket.sendto(ack_packet, self.server_address)
        print("连接已建立")

    def _close_connection(self):
        # 模拟TCP的四次挥手
        # 发送FIN
        fin_packet = self._create_packet(seq=self.total_packets + 1, ack=0, syn=0, fin=1, data=b'')
        self.client_socket.sendto(fin_packet, self.server_address)

        # 接收ACK
        while True:
            try:

                data, addr = self.client_socket.recvfrom(1024)
                packet = self._parse_packet(data)
                if packet['ack']:
                    break
            except socket.timeout:
                # 超时重传FIN
                self.client_socket.sendto(fin_packet, self.server_address)

        # 接收FIN
        while True:
            try:
                data, addr = self.client_socket.recvfrom(1024)
                packet = self._parse_packet(data)
                if packet['fin']:
                    break
            except socket.timeout:
                pass

        # 发送ACK
        ack_packet = self._create_packet(seq=self.total_packets + 2, ack=packet['seq'] + 1, syn=0, fin=0, data=b'')
        self.client_socket.sendto(ack_packet, self.server_address)
        print("连接已关闭")

    def _send_packet(self, seq_num, is_retransmit=False):
        # 创建数据包
        start_byte = (seq_num - 1) * 80 + 1
        end_byte = seq_num * 80
        data = f"Data from byte {start_byte} to {end_byte}".ljust(80, 'X').encode()
        packet = self._create_packet(seq=seq_num, ack=0, syn=0, fin=0, data=data)

        # 记录发送时间
        self.window[seq_num] = {
            'send_time': time.time(),
            'data': data
        }

        # 发送数据包
        self.client_socket.sendto(packet, self.server_address)
        self.total_attempts += 1

        # 打印发送信息
        if is_retransmit:
            print(f"重传第{seq_num}个（第{start_byte}-{end_byte}字节）数据包")
        else:
            print(f"已接收第{seq_num}个（第{start_byte}-{end_byte}字节）数据包")

    def _create_packet(self, seq, ack, syn, fin, data):
        # 自定义协议首部格式
        # 4字节序列号 + 4字节确认号 + 1字节标志位 + 4字节时间戳 + 数据

        # 1. 组合标志位：syn占第1位，fin占第0位（1字节）
        flags = (syn << 1) | fin
        # 2. 获取当前时间戳（4字节整数）
        timestamp = int(time.time())
        # 3. 打包首部：大端序(!)，格式为 4字节seq + 4字节ack + 1字节flags + 4字节timestamp
        header = struct.pack('!IIBI', seq, ack, flags, timestamp)
        # 4. 拼接首部和数据，返回完整数据包
        return header + data

    def _parse_packet(self, packet_data):
        # 解析数据包
        # 1. 提取前13字节作为首部（固定长度）
        header = packet_data[:13]
        # 2. 按大端序(!)解包首部：4字节seq + 4字节ack + 1字节flags + 4字节timestamp
        seq, ack, flags, timestamp = struct.unpack('!IIBI', header)
        # 3. 解析标志位：通过位运算提取syn和fin
        syn = (flags & 0x02) >> 1
        fin = flags & 0x01
        # 4. 返回包含各字段的字典
        return {
            'seq': seq,# 序列号
            'ack': ack,# 确认号
            'syn': syn,# 同步标志
            'fin': fin,# 结束标志
            'timestamp': timestamp# 时间戳
        }

    def _print_summary(self):
        # 计算并打印汇总信息
        if not self.rtt_data:
            print("没有收到任何确认，无法计算统计信息")
            return

        # 计算丢包率
        packet_loss_rate = (self.total_attempts - self.total_packets) / self.total_attempts * 100

        # 使用pandas计算RTT统计量
        rtt_series = pd.Series(self.rtt_data)
        max_rtt = rtt_series.max()
        min_rtt = rtt_series.min()
        avg_rtt = rtt_series.mean()
        std_rtt = rtt_series.std()

        # 打印汇总信息
        print("\n【汇总】")
        print(f"- 丢包率：{packet_loss_rate:.2f}%")
        print(f"- 最大RTT：{max_rtt:.2f} ms")
        print(f"- 最小RTT：{min_rtt:.2f} ms")
        print(f"- 平均RTT：{avg_rtt:.2f} ms")
        print(f"- RTT的标准差：{std_rtt:.2f} ms")


if __name__ == "__main__":
    client = UDPClient()
    client.start()