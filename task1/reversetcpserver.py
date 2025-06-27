import socket
import struct
import threading

# 报文类型
TYPE_INIT = 1
TYPE_AGREE = 2
TYPE_REQ = 3
TYPE_RESP = 4


def recv_all(sock, length):
    data = b''
    while len(data) < length:
        more = sock.recv(length - len(data))
        if not more:
            raise EOFError('Socket closed unexpectedly')
        data += more
    return data


def handle_client(conn, addr):
    try:
        print(f"[连接] 来自 {addr}")

        # 接收 Initialization
        header = recv_all(conn, 5)
        packet_type, total_chunks = struct.unpack('!BI', header)
        if packet_type != TYPE_INIT:
            print("收到错误类型的初始化报文")
            return

        print(f"[{addr}] 任务总块数: {total_chunks}")
        conn.sendall(struct.pack('!B', TYPE_AGREE))

        # 逐块处理
        for i in range(total_chunks):
            head = recv_all(conn, 5)
            packet_type, length = struct.unpack('!BI', head)
            if packet_type != TYPE_REQ:
                print("收到错误类型的数据请求")
                return

            data = recv_all(conn, length)
            reversed_data = data[::-1]#反向排列

            response = struct.pack('!BI', TYPE_RESP, len(reversed_data)) + reversed_data
            conn.sendall(response)

    except Exception as e:
        print(f"[错误] {e}")
    finally:
        conn.close()
        print(f"[断开] {addr}")

def main():
    # 用户输入端口号
    port = int(input("请输入服务端监听端口号（如12345）：").strip())
    host = '0.0.0.0'  # 监听所有IP

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((host, port))
    server_socket.listen(5)
    print(f"[启动] TCP服务端监听端口 {port}，等待客户端连接...")

    while True:
        client_socket, addr = server_socket.accept() # 主线程阻塞等待新连接
        threading.Thread(target=handle_client, args=(client_socket, addr)).start()# 为每个客户端创建新线程


if __name__ == "__main__":
    main()
