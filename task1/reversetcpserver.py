import socket
import struct
import threading

# 报文类型
TYPE_INIT = 1# 初始化报文，客户端发送总块数
TYPE_AGREE = 2 # 同意报文，服务器确认初始化
TYPE_REQ = 3  # 请求报文，客户端发送数据块
TYPE_RESP = 4# 响应报文，服务器返回反转后的数据块


def recv_all(sock, length):
    # 接收指定长度的数据，确保完整接收
    # 参数：
    # - sock: TCP 套接字
    # - length: 期望接收的字节数
    # 返回：接收到的字节数据
    data = b''
    while len(data) < length:
        more = sock.recv(length - len(data)) # 接收剩余字节
        if not more:
            raise EOFError('Socket closed unexpectedly') # 连接意外关闭
        data += more
    return data


def handle_client(conn, addr):
    # 处理单个客户端连接，运行在独立线程中
    # 参数：
    # - conn: 客户端的 TCP 套接字
    # - addr: 客户端地址（IP 和端口）
    try:
        print(f"[连接] 来自 {addr}")

        # 接收初始化报文（5 字节：1 字节类型 + 4 字节总块数）
        header = recv_all(conn, 5)
        packet_type, total_chunks = struct.unpack('!BI', header) # 大端序解包
        if packet_type != TYPE_INIT:
            print("收到错误类型的初始化报文")
            return

        print(f"[{addr}] 任务总块数: {total_chunks}")
        # 发送 AGREE 报文（1 字节类型）
        conn.sendall(struct.pack('!B', TYPE_AGREE))

        # 发送 AGREE 报文（1 字节类型）
        for i in range(total_chunks):
            # 接收请求报文头部（5 字节：1 字节类型 + 4 字节数据长度）
            head = recv_all(conn, 5)
            packet_type, length = struct.unpack('!BI', head)
            if packet_type != TYPE_REQ:
                print("收到错误类型的数据请求")
                return

            # 接收数据块
            data = recv_all(conn, length)
            reversed_data = data[::-1]# 反转数据块内容
            # 构造响应报文（1 字节类型 + 4 字节长度 + 反转数据）
            response = struct.pack('!BI', TYPE_RESP, len(reversed_data)) + reversed_data
            conn.sendall(response)# 发送响应

    except Exception as e:
        print(f"[错误] {e}")
    finally:
        conn.close()# 关闭客户端连接
        print(f"[断开] {addr}")

def main():
    # 主函数，启动 TCP 服务器
    # 获取用户输入的监听端口
    port = int(input("请输入服务端监听端口号（如12345）：").strip())
    host = '0.0.0.0' # 监听所有 IP 地址

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((host, port))# 绑定地址和端口
    server_socket.listen(5)# 监听队列大小为 5
    print(f"[启动] TCP服务端监听端口 {port}，等待客户端连接...")

    # 主循环，接受客户端连接
    while True:
        client_socket, addr = server_socket.accept() # 阻塞等待新连接
        threading.Thread(target=handle_client, args=(client_socket, addr)).start()# 为每个客户端创建新线程处理


if __name__ == "__main__":
    main()
