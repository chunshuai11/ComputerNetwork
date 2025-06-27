import socket
import time
import struct
import random


class UDPServer:
    def __init__(self):
        #初始化 UDP 服务器
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)#创建UDP套接字
        self.buffer = {}  #存储已接收但未按序排列的数据包
        self.expected_seq = 1  #期望接收的下一个序列号
        self.loss_rate = 0.2  #丢包率20%
        self.server_address = None#服务器地址（IP和端口）

    def start(self):
        #主方法，控制服务器的运行流程
        #获取用户输入的服务器IP和端口
        server_ip = input("请输入服务器IP地址: ")
        server_port = int(input("请输入服务器端口号: "))
        self.server_address = (server_ip, server_port)

        #绑定套接字到指定地址
        self.server_socket.bind(self.server_address)
        print(f"服务器已启动，监听地址: {server_ip}:{server_port}")

        #模拟TCP三次握手
        self._handle_connection_establishment()

        #数据接收循环
        try:
            while True:
                data, client_address = self.server_socket.recvfrom(1024)#接收客户端数据
                packet = self._parse_packet(data)#解析数据包

                #处理FIN包
                if packet['fin']:
                    self._handle_connection_closure(client_address, packet)
                    break

                #模拟20%丢包率
                if random.random() < self.loss_rate:
                    print(f"模拟丢包: 第{packet['seq']}个数据包")
                    continue
                # 处理数据包
                self._handle_packet(client_address, packet)

        except KeyboardInterrupt:
            print("\n程序被用户中断")
        finally:
            self.server_socket.close()#关闭套接字

    def _handle_connection_establishment(self):
        #模拟TCP三次握手
        #1. 接收客户端的SYN包
        while True:
            data, client_address = self.server_socket.recvfrom(1024)
            packet = self._parse_packet(data)
            if packet['syn']:#检查是否为SYN包
                break

        #2. 发送SYN+ACK包
        syn_ack_packet = self._create_packet(seq=1, ack=packet['seq'] + 1, syn=1, fin=0, data=b'')
        self.server_socket.sendto(syn_ack_packet, client_address)

        #3. 接收客户端的ACK包
        while True:
            try:
                self.server_socket.settimeout(1.0)#设置1秒超时
                data, client_address = self.server_socket.recvfrom(1024)
                packet = self._parse_packet(data)
                if packet['ack']:#检查是否为ACK包
                    break
            except socket.timeout:
                # 超时重传SYN+ACK
                self.server_socket.sendto(syn_ack_packet, client_address)

        print("连接已建立")

    def _handle_connection_closure(self, client_address, packet):
        # 模拟 TCP 四次挥手
        # 1. 发送 ACK 包，确认客户端的 FIN
        ack_packet = self._create_packet(seq=packet['ack'], ack=packet['seq'] + 1, syn=0, fin=0, data=b'')
        self.server_socket.sendto(ack_packet, client_address)

        # 2. 发送 FIN 包
        fin_packet = self._create_packet(seq=packet['ack'] + 1, ack=packet['seq'] + 1, syn=0, fin=1, data=b'')
        self.server_socket.sendto(fin_packet, client_address)

        # 3. 接收客户端的 ACK 包
        while True:
            try:
                self.server_socket.settimeout(1.0)
                data, _ = self.server_socket.recvfrom(1024)
                packet = self._parse_packet(data)
                if packet['ack']:# 检查是否为 ACK 包
                    break
            except socket.timeout:
                # 超时重传 FIN 包
                self.server_socket.sendto(fin_packet, client_address)

        print("连接已关闭")

    def _handle_packet(self, client_address, packet):
        # 处理接收到的数据包（实现 GBN 协议的累计确认）
        # 参数：
        # - client_address: 客户端地址
        # - packet: 解析后的数据包
        seq_num = packet['seq']

        # 情况 1：收到期望的或之前的包（可能是重传
        if seq_num <= self.expected_seq:
            # 存储数据包
            self.buffer[seq_num] = packet# 存储数据包

            # 按序交付：从expected_seq开始连续交付
            while self.expected_seq in self.buffer:
                # 处理数据（这里只是打印）
                start_byte = (self.expected_seq - 1) * 80 + 1 # 数据起始字节
                end_byte = self.expected_seq * 80 # 数据结束字节
                print(f"已接收第{self.expected_seq}个（第{start_byte}-{end_byte}字节）数据包")
                del self.buffer[self.expected_seq]# 删除已交付的数据包
                self.expected_seq += 1# 更新期望序号

            # 发送累计确认
            ack_packet = self._create_packet(
                seq=packet['ack'],
                ack=self.expected_seq - 1, # 确认最大的连续接收序号
                syn=0,
                fin=0,
                data=b''
            )
            self.server_socket.sendto(ack_packet, client_address)
        else:
            # 情况 2：收到乱序数据包，缓存并发送当前确认
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
        # 创建自定义协议数据包
        # 参数：
        # - seq: 序列号（4 字节）
        # - ack: 确认号（4 字节）
        # - syn: 同步标志（1 位）
        # - fin: 结束标志（1 位）
        # - data: 数据部分
        flags = (syn << 1) | fin# 组合标志位
        timestamp = int(time.time())# 获取当前时间戳
        header = struct.pack('!IIBI', seq, ack, flags, timestamp)# 大端序打包首部
        return header + data# 拼接首部和数据

    def _parse_packet(self, packet_data):
        # 解析接收到的数据包
        # 参数：
        # - packet_data: 接收到的字节数据
        # 返回：包含 seq、ack、syn、fin、timestamp、data 的字典
        header = packet_data[:13]# 提取 13 字节首部
        seq, ack, flags, timestamp = struct.unpack('!IIBI', header)# 大端序解包
        syn = (flags & 0x02) >> 1# 提取 syn 标志
        fin = flags & 0x01 # 提取 fin 标志
        return {
            'seq': seq,
            'ack': ack,
            'syn': syn,
            'fin': fin,
            'timestamp': timestamp,
            'data': packet_data[13:]# 提取数据部分
        }


if __name__ == "__main__":
    server = UDPServer()
    server.start()