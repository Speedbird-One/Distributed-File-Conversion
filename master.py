import socket
import threading
import ssl
import struct
import protocol

MASTER_HOST = "127.0.0.1"
MASTER_PORT = 5000
WORKER_HOST = "127.0.0.1"
WORKER_PORT = 6000


def recv_exact(sock, size):
    data = b""
    while len(data) < size:
        packet = sock.recv(size - len(data))
        if not packet:
            return None
        data += packet
    return data


def handle_client(client_socket, client_addr):
    print(f"[MASTER] Handling connection from {client_addr}")

    # ===== ADDED: basic timeout =====
    client_socket.settimeout(60)

    try:
        # Read 94-byte header
        header = recv_exact(client_socket, protocol.HEADER_SIZE)
        if not header:
            return

        header_info = protocol.parse_header(header)

        # ===== ADDED: VALIDATIONS =====
        if not protocol.validate_version(header_info["version"]):
            raise Exception("Unsupported protocol version")

        if not protocol.validate_auth_token(header_info["auth_token"]):
            raise Exception("Invalid authentication token")

        if not protocol.validate_operation(header_info["operation"]):
            raise Exception("Invalid operation requested")

        file_size = header_info["file_size"]
        print(f"[MASTER] File: {header_info['filename']} | Size: {file_size}")

        # ===== ADDED: Job ID tracking =====
        import uuid

        job_id = str(uuid.uuid4())
        print(f"[MASTER] Job ID: {job_id}")

        # Connect to worker
        worker_context = ssl.create_default_context()
        worker_context.check_hostname = False
        worker_context.verify_mode = ssl.CERT_NONE

        worker_sock_raw = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # ===== ADDED: timeout =====
        worker_sock_raw.settimeout(60)

        worker_socket = worker_context.wrap_socket(
            worker_sock_raw, server_hostname=WORKER_HOST
        )
        worker_socket.connect((WORKER_HOST, WORKER_PORT))

        # Forward header
        worker_socket.sendall(header)

        # Forward exactly file_size bytes to worker
        bytes_forwarded = 0
        while bytes_forwarded < file_size:
            chunk = client_socket.recv(min(65536, file_size - bytes_forwarded))
            if not chunk:
                break
            worker_socket.sendall(chunk)
            bytes_forwarded += len(chunk)

        print(f"[MASTER] Forwarded {bytes_forwarded} bytes to worker")

        # Read 8-byte size from worker
        size_bytes = recv_exact(worker_socket, 8)
        if not size_bytes:
            raise Exception("Worker did not send response size")

        response_size = struct.unpack("!Q", size_bytes)[0]
        print(f"[MASTER] Worker response size: {response_size} bytes")

        # Forward size + data back to client
        client_socket.sendall(size_bytes)

        bytes_returned = 0
        while bytes_returned < response_size:
            chunk = worker_socket.recv(min(65536, response_size - bytes_returned))
            if not chunk:
                break
            client_socket.sendall(chunk)
            bytes_returned += len(chunk)

        worker_socket.close()
        print(f"[MASTER] Job complete for {client_addr}\n")

    except Exception as e:
        print(f"[MASTER] Error: {e}")

        # ===== ADDED: Graceful error response =====
        try:
            error_msg = f"ERROR: {str(e)}".encode()
            client_socket.sendall(struct.pack("!Q", len(error_msg)))
            client_socket.sendall(error_msg)
        except:
            pass

    finally:
        client_socket.close()


def start_master():
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.load_cert_chain(certfile="server.crt", keyfile="server.key")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_sock:
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind((MASTER_HOST, MASTER_PORT))
        server_sock.listen(20)
        print(f"[MASTER] Secure Brain online. Listening on {MASTER_PORT}...")

        while True:
            client_sock_raw, addr = server_sock.accept()

            # ===== ADDED: wrap safely =====
            try:
                secure_client = context.wrap_socket(client_sock_raw, server_side=True)
            except Exception as e:
                print(f"[MASTER] TLS handshake failed: {e}")
                client_sock_raw.close()
                continue

            client_thread = threading.Thread(
                target=handle_client, args=(secure_client, addr)
            )
            client_thread.start()


if __name__ == "__main__":
    start_master()
