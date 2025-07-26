import json
import socket
import threading

HOST = "127.0.0.1"
PORT = 12345  # MCPHawk should sniff this port


def handle_client(conn, addr):
    print(f"[DUMMY MCP] Connection from {addr}")
    try:
        while True:
            data = conn.recv(1024)
            if not data:
                break

            raw_msg = data.decode(errors="ignore").strip()
            print(f"[DUMMY MCP] Received: {raw_msg}")

            try:
                # Parse incoming JSON-RPC request
                request = json.loads(raw_msg)
                request_id = request.get("id")

                # Build realistic JSON-RPC response
                response = {
                    "jsonrpc": "2.0",
                    "result": "ok",
                    "id": request_id  # echo back same id if present
                }

            except json.JSONDecodeError:
                print("[DUMMY MCP] Invalid JSON received, sending error response")
                response = {
                    "jsonrpc": "2.0",
                    "error": {"code": -32700, "message": "Parse error"},
                    "id": None
                }

            # Send back response
            conn.sendall((json.dumps(response) + "\n").encode())

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

