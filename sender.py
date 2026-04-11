import socket
import ssl
import struct
import os
import protocol


def recv_exact(sock, size):
    data = b""
    while len(data) < size:
        packet = sock.recv(size - len(data))
        if not packet:
            return None
        data += packet
    return data


# ===== ADDED: FILE TYPE DETECTION (LIGHT VERSION FOR UI) =====
def detect_file_type(filepath):
    ext = os.path.splitext(filepath)[1].lower()

    if ext in [".jpg", ".jpeg", ".png", ".webp"]:
        return "image"
    elif ext == ".txt":
        return "txt"
    elif ext == ".pdf":
        return "pdf"
    else:
        return "unknown"


def run_client(filepath, host="127.0.0.1", port=5000):
    file_type = detect_file_type(filepath)
    ext = os.path.splitext(filepath)[1].lower()

    valid_options = []

    # ===== DYNAMIC FILTERED MENU =====
    if file_type == "image":
        print("\nSelect Operation:")
        if ext not in [".jpg", ".jpeg"]:
            print("1 → Convert to JPG")
            valid_options.append(1)
        if ext != ".png":
            print("2 → Convert to PNG")
            valid_options.append(2)
        if ext != ".webp":
            print("3 → Convert to WEBP")
            valid_options.append(3)

    elif file_type == "txt":
        print("\nSelect Operation:\n4 → TXT → PDF")
        valid_options.append(4)

    elif file_type == "pdf":
        print("\nSelect Operation:\n5 → PDF → TXT")
        valid_options.append(5)

    else:
        print("Unsupported file type.")
        return

    try:
        operation = int(input("\nSelect operation: "))
        if operation not in valid_options:
            print(f"Invalid selection for a {ext} file.")
            return
    except ValueError:
        print("Invalid input.")
        return

    file_size = os.path.getsize(filepath)
    header = protocol.build_header(filepath, operation)

    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        secure_sock = context.wrap_socket(s, server_hostname=host)
        try:
            secure_sock.connect((host, port))

            # Send header
            secure_sock.sendall(header)

            # Send file
            bytes_sent = 0
            with open(filepath, "rb") as f:
                while chunk := f.read(65536):
                    secure_sock.sendall(chunk)
                    bytes_sent += len(chunk)

            print(f"Sent {os.path.basename(filepath)} ({bytes_sent} bytes). Waiting...")

            # Receive response size
            size_bytes = recv_exact(secure_sock, 8)
            if not size_bytes:
                print("Error: No response from server.")
                return

            response_size = struct.unpack("!Q", size_bytes)[0]

            # ===== FIXED EXTENSION MAP =====
            ext_map = {1: ".jpg", 2: ".png", 3: ".webp", 4: ".pdf", 5: ".txt"}

            new_ext = ext_map.get(operation, ".bin")

            original_name_no_ext = os.path.splitext(os.path.basename(filepath))[0]
            output_path = f"converted_{original_name_no_ext}{new_ext}"

            # Receive file
            bytes_received = 0
            with open(output_path, "wb") as f:
                while bytes_received < response_size:
                    data = secure_sock.recv(min(65536, response_size - bytes_received))
                    if not data:
                        break
                    f.write(data)
                    bytes_received += len(data)

            print(f"Success! Saved as: {output_path} ({bytes_received} bytes)")

        except ConnectionRefusedError:
            print("Error: Could not connect to Master.")
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    path = input("Enter file path: ")
    run_client(path)
