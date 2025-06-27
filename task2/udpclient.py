import socket
import time
import struct

import pandas as pd


class UDPClient:
    #初始化UDP客户端
    def __init__(self):
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) #创建UDP套接字
        self.client_socket.settimeout(0.3)  #设置300ms超时，用于检测数据包是否丢失
        self.base = 1 #滑动窗口的基序号，表示最早未确认的数据包
        self.next_seq = 1#下一个要发送的数据包序号
        self.buffer_size = 5#滑动窗口大小，最多存储 5 个未确认数据包
        self.window = {} #字典，存储已发送但未确认的数据包（键：序号，值：发送时间和数据）
        self.rtt_data = [] #列表，存储每次确认的往返时延（RTT）
        self.total_packets = 30  #总共要发送的数据包数量
        self.total_attempts = 0   #总发送尝试次数（包括重传）
        self.server_address = None #服务器地址（IP 和端口）

    def start(self):
        #主方法，控制客户端的运行流程
        #获取用户输入的服务器IP和端口
        server_ip = input("请输入服务器IP地址: ")
        server_port = int(input("请输入服务器端口号: "))
        self.server_address = (server_ip, server_port)#设置服务器地址

        #模拟TCP三次握手，建立连接
        self._establish_connection()

        #数据传输循环
        try:
            while self.base <= self.total_packets:#直到所有数据包被确认
                # 发送窗口内的数据包（最多 5 个）
                while self.next_seq < self.base + self.buffer_size and self.next_seq <= self.total_packets:
                    self._send_packet(self.next_seq)#发送新数据包
                    self.next_seq += 1#增加下一个发送序号

                #等待服务器的确认包
                try:
                    data, addr = self.client_socket.recvfrom(1024)#接收数据包（最大 1024 字节）
                    #提取头部信息
                    ack_packet = self._parse_packet(data)#解析确认包
                    if ack_packet['ack'] >= self.base:#如果确认序号 >= 窗口基序号
                        seq_acknowledged = ack_packet['ack']#获取确认的序号
                        if seq_acknowledged in self.window:
                            #计算RTT（单位：毫秒）
                            send_time = self.window[seq_acknowledged]['send_time']
                            rtt = (time.time() - send_time) * 1000  # 转换为毫秒
                            self.rtt_data.append(rtt)

                            #打印确认信息
                            start_byte = (seq_acknowledged - 1) * 80 + 1 #数据起始字节
                            end_byte = seq_acknowledged * 80#数据结束字节
                            print(
                                f"第{seq_acknowledged}个（第{start_byte}-{end_byte}字节），server端已经收到，RTT是 {rtt:.2f} ms")

                            #移除已确认的数据包
                            for seq in list(self.window.keys()):
                                if seq <= seq_acknowledged:# 删除所有 <= 确认序号的包（GBN 累计确认）
                                    del self.window[seq]

                            #滑动窗口，更新基序号
                            self.base = seq_acknowledged + 1
                except socket.timeout:
                    #超时处理：重传窗口内最早未确认的数据包
                    seq_to_retransmit = self.base
                    if seq_to_retransmit in self.window:
                        self._send_packet(seq_to_retransmit, is_retransmit=True)

        except KeyboardInterrupt:
            print("\n程序被用户中断")
        finally:
            # 无论如何都执行连接关闭和统计
            self._close_connection() # 模拟 TCP 四次挥手
            self._print_summary() # 打印传输统计信息
            self.client_socket.close()# 关闭套接字

    def _establish_connection(self):
        # 模拟 TCP 三次握手，建立可靠连接
        # 1. 发送 SYN 包（序列号=0，syn=1）
        syn_packet = self._create_packet(seq=0, ack=0, syn=1, fin=0, data=b'')
        self.client_socket.sendto(syn_packet, self.server_address)

        # 2. 等待服务器的 SYN+ACK 包
        while True:
            try:
                data, addr = self.client_socket.recvfrom(1024)
                packet = self._parse_packet(data)
                if packet['syn'] and packet['ack']:# 检查是否为 SYN+ACK 包
                    break
            except socket.timeout:
                # 超时重传SYN
                self.client_socket.sendto(syn_packet, self.server_address)

        # 3. 发送 ACK 包（序列号=1，确认号=1）
        ack_packet = self._create_packet(seq=1, ack=1, syn=0, fin=0, data=b'')
        self.client_socket.sendto(ack_packet, self.server_address)
        print("连接已建立")

    def _close_connection(self):
        # 模拟TCP四次挥手，关闭连接
        # 1. 发送FIN包（序列号=total_packets+1，fin=1）
        fin_packet = self._create_packet(seq=self.total_packets + 1, ack=0, syn=0, fin=1, data=b'')
        self.client_socket.sendto(fin_packet, self.server_address)

        # 2. 等待服务器的ACK包
        while True:
            try:
                data, addr = self.client_socket.recvfrom(1024)
                packet = self._parse_packet(data)
                if packet['ack']: # 检查是否为ACK包
                    break
            except socket.timeout:
                # 超时重传 FIN 包
                self.client_socket.sendto(fin_packet, self.server_address)

        # 3. 等待服务器的 FIN 包
        while True:
            try:
                data, addr = self.client_socket.recvfrom(1024)
                packet = self._parse_packet(data)
                if packet['fin']:# 检查是否为 FIN 包
                    break
            except socket.timeout:
                pass# 忽略超时，继续等待

        # 4. 发送最终 ACK 包
        ack_packet = self._create_packet(seq=self.total_packets + 2, ack=packet['seq'] + 1, syn=0, fin=0, data=b'')
        self.client_socket.sendto(ack_packet, self.server_address)
        print("连接已关闭")

    def _send_packet(self, seq_num, is_retransmit=False):
        # 发送数据包并记录发送时间
        # 参数：
        # -seq_num: 数据包序列号
        # -is_retransmit: 是否为重传包
        start_byte = (seq_num - 1) * 80 + 1#计算数据起始字节
        end_byte = seq_num * 80 #计算数据结束字节
        data = f"Data from byte {start_byte} to {end_byte}".ljust(80, 'X').encode()# 生成 80 字节数据
        packet = self._create_packet(seq=seq_num, ack=0, syn=0, fin=0, data=data) #创建数据包

        #记录发送时间和数据
        self.window[seq_num] = {
            'send_time': time.time(),
            'data': data
        }

        #发送数据包
        self.client_socket.sendto(packet, self.server_address)
        self.total_attempts += 1#增加发送尝试计数

        #打印发送信息
        if is_retransmit:
            print(f"重传第{seq_num}个（第{start_byte}-{end_byte}字节）数据包")
        else:
            print(f"已发送第{seq_num}个（第{start_byte}-{end_byte}字节）数据包")

    def _create_packet(self, seq, ack, syn, fin, data):
        #创建自定义协议数据包
        #参数：
        # -seq: 序列号（4字节）
        # -ack: 确认号（4字节）
        # -syn: 同步标志（1位）
        # -fin: 结束标志（1位）
        # -data: 数据部分
        #首部格式：4字节seq+4字节ack+1字节flags+4字节timestamp
        flags = (syn << 1) | fin #组合标志位：syn占第1位，fin占第0位
        #获取当前时间戳（整数，4 字节）
        timestamp = int(time.time())
        #使用大端序打包首部
        header = struct.pack('!IIBI', seq, ack, flags, timestamp)
        #拼接首部和数据
        return header + data

    def _parse_packet(self, packet_data):
        #解析接收到的数据包
        #参数：
        #-packet_data: 接收到的字节数据
        #返回：包含seq、ack、syn、fin、timestamp的字典
        header = packet_data[:13] # 提取前 13 字节作为首部
        #2. 按大端序(!)解包首部：4字节seq+4字节ack+1字节flags+4字节timestamp
        seq, ack, flags, timestamp = struct.unpack('!IIBI', header) #大端序解包
        syn = (flags & 0x02) >> 1#提取syn标志（第1位）
        fin = flags & 0x01#提取fin标志（第0位）
        return {
            'seq': seq,#序列号
            'ack': ack,#确认号
            'syn': syn,#同步标志
            'fin': fin,#结束标志
            'timestamp': timestamp#时间戳
        }

    def _print_summary(self):
        # 打印传输统计信息
        if not self.rtt_data:
            print("没有收到任何确认，无法计算统计信息")
            return

        #计算丢包率
        packet_loss_rate = (self.total_attempts - self.total_packets) / self.total_attempts * 100

        #使用pandas计算RTT统计量
        rtt_series = pd.Series(self.rtt_data)
        max_rtt = rtt_series.max()#最大RTT
        min_rtt = rtt_series.min()#最小RTT
        avg_rtt = rtt_series.mean()#平均RTT
        std_rtt = rtt_series.std()#RTT标准差

        #打印汇总信息
        print("\n【汇总】")
        print(f"- 丢包率：{packet_loss_rate:.2f}%")
        print(f"- 最大RTT：{max_rtt:.2f} ms")
        print(f"- 最小RTT：{min_rtt:.2f} ms")
        print(f"- 平均RTT：{avg_rtt:.2f} ms")
        print(f"- RTT的标准差：{std_rtt:.2f} ms")


if __name__ == "__main__":
    client = UDPClient()
    client.start()