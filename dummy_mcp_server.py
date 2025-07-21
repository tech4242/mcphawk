import socket
import threading

HOST = "127.0.0.1"
PORT = 12345  # MCP-Shark should sniff this port


def handle_client(conn, addr):
    print(f"[DUMMY MCP] Connection from {addr}")
    try:
        while True:
            data = conn.recv(1024)
            if not data:
                break
            print(f"[DUMMY MCP] Received: {data.decode(errors='ignore')}")
            # Echo back something MCP-like
            response = '{"jsonrpc":"2.0","result":"ok"}\n'.encode()
            conn.sendall(response)
    finally:
        conn.close()


def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen()
    print(f"[DUMMY MCP] Listening on {HOST}:{PORT}")
    while True:
        conn, addr = server.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()


if __name__ == "__main__":
    start_server()
