import socket
import struct
import random
import os

# 定义报文类型常量
TYPE_INIT = 1  # 初始化报文，发送总块数
TYPE_AGREE = 2  # 同意报文，服务器确认
TYPE_REQ = 3   # 请求报文，发送数据块
TYPE_RESP = 4  # 响应报文，接收反转数据块

def recv_all(sock, length):
    # 接收指定长度的数据，确保完整接收
    # 参数：
    # - sock: TCP 套接字
    # - length: 期望接收的字节数
    # 返回：接收到的字节数据
    data = b''
    while len(data) < length:
        more = sock.recv(length - len(data))  # 接收剩余字节
        if not more:
            raise EOFError('意外关闭')  # 连接意外关闭
        data += more
    return data

def main():
    try:
        # 用户输入参数
        server_ip = input("请输入服务器IP地址（如127.0.0.1）：").strip()
        server_port = int(input("请输入服务器端口号（如12345）：").strip())
        input_file = input("请输入要发送的ASCII文本文件名（如test.txt）：").strip()
        Lmin = int(input("请输入每块最小长度Lmin（如5）：").strip())
        Lmax = int(input("请输入每块最大长度Lmax（如10）：").strip())

        # 验证输入
        if not os.path.exists(input_file):
            print(f"错误：文件 {input_file} 不存在")
            return
        if Lmin <= 0 or Lmax < Lmin:
            print("错误：Lmin 必须大于 0 且不大于 Lmax")
            return
        if server_port < 1024 or server_port > 65535:
            print("错误：端口号必须在 1024-65535 之间")
            return

        # 读取文件并验证 ASCII 可打印字符
        with open(input_file, 'rb') as f:
            content = f.read()
            for b in content:
                if b < 32 or b > 126:
                    if b not in (10, 13):   # 允许换行符（\n）和回车符（\r）
                        raise ValueError(f"文件包含非 ASCII 可打印字符 (字节值: {b})")

        # 按 Lmin 和 Lmax 分块
        chunks = []
        index = 0
        while index < len(content):
            remaining = len(content) - index # 剩余字节数
            max_size = min(Lmax, remaining)  # 最大块大小
            min_size = min(Lmin, remaining) # 最小块大小
            if min_size > max_size:
                min_size = max_size
            # 随机选择块大小
            length = random.randint(min_size, max_size) if min_size < max_size else min_size
            chunk = content[index:index + length]# 提取块
            chunks.append(chunk)
            index += length

        total_chunks = len(chunks)# 总块数
        print(f"分块完成，共 {total_chunks} 块，块大小: {[len(c) for c in chunks]}")
        for i, chunk in enumerate(chunks):
            print(f"块 {i+1}: {chunk.decode('ascii', errors='replace')}")# 打印每块内容

        # 建立 TCP 连接
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.connect((server_ip, server_port))# 连接服务器
        except socket.error as e:
            print(f"连接服务器失败: {e}")
            return

        # 发送初始化报文（1 字节类型 + 4 字节总块数）
        init_packet = struct.pack('!BI', TYPE_INIT, total_chunks)
        sock.sendall(init_packet)

        # 接收服务器的 AGREE 报文
        resp_type = recv_all(sock, 1)
        if resp_type[0] != TYPE_AGREE:
            print("未收到 AGREE 报文")
            sock.close()
            return

        print(f"已与服务器建立通信，共有 {total_chunks} 块")

        # 逐块发送请求并接收反转响应
        for i, chunk in enumerate(chunks):
            # 发送 ReverseRequest 报文（1 字节类型 + 4 字节长度 + 数据）
            packet = struct.pack('!BI', TYPE_REQ, len(chunk)) + chunk
            sock.sendall(packet)

            # 接收 ReverseAnswer 报文
            resp_type = recv_all(sock, 1)
            if resp_type[0] != TYPE_RESP:
                print(f"块 {i+1} 未收到正确的 ReverseAnswer 报文")
                break
            length = struct.unpack('!I', recv_all(sock, 4))[0] # 接收数据长度
            reversed_data = recv_all(sock, length)# 接收反转数据
            print(f"{i+1}: {reversed_data.decode('ascii', errors='replace')}")# 打印反转结果

        # 生成反转文件（整体反转，保持行结构）
        with open(input_file, 'r', encoding='ascii') as f:
            lines = f.readlines()
        # 反转整个文件内容（按字符反转）
        reversed_content = ''.join(lines)[::-1]
        reversed_lines = reversed_content.splitlines()# 按行分割反转内容
        # 写入反转文件，确保每行之间只有一个换行符
        with open("reversed.txt", "w", encoding='ascii', newline='\n') as f:
            for i, line in enumerate(reversed_lines):
                f.write(line.rstrip())# 去除行尾空白
                if i < len(reversed_lines) - 1:  # 避免最后多余换行
                    f.write('\n')

        print("客户端结束，反转结果保存在 reversed.txt")

    except ValueError as e:
        print(f"输入错误: {e}")
    except IOError as e:
        print(f"文件错误: {e}")
    except Exception as e:
        print(f"运行错误: {e}")
    finally:
        sock.close()# 关闭套接字

if __name__ == "__main__":
    main()