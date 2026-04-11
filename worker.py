import socket
import ssl
import struct
import protocol
import threading
import io
import os
from PIL import Image
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

# 🔥 BETTER PDF LIB
import pdfplumber

HOST = "127.0.0.1"
PORT = 6000


def recv_exact(conn, size):
    data = b""
    while len(data) < size:
        packet = conn.recv(size - len(data))
        if not packet:
            return None
        data += packet
    return data


def detect_file_type(file_data):
    if file_data.startswith(b"%PDF"):
        return "pdf"
    if file_data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if file_data.startswith(b"\x89PNG"):
        return "png"
    if file_data.startswith(b"RIFF") and file_data[8:12] == b"WEBP":
        return "webp"

    try:
        file_data.decode("utf-8")
        return "txt"
    except:
        return "unknown"


def process_file(data, filename, operation):
    file_type = detect_file_type(data)
    print(f"[WORKER DEBUG] {filename} | Type: {file_type} | Op: {operation}")

    # ===== PDF → TXT =====
    if file_type == "pdf":
        if operation != 5:
            return b"ERROR: PDF detected. Use Op 5."

        try:
            text_content = []

            with pdfplumber.open(io.BytesIO(data)) as pdf:
                for page in pdf.pages:
                    extracted = page.extract_text()
                    if extracted:
                        text_content.append(extracted)

            return "\n".join(text_content).encode("utf-8")

        except Exception as e:
            return f"ERROR: PDF extraction failed - {str(e)}".encode()

    # ===== TXT → PDF =====
    elif file_type == "txt":
        if operation != 4:
            return b"ERROR: Text detected. Use Op 4."

        try:
            text = data.decode("utf-8", errors="ignore")

            output_stream = io.BytesIO()
            doc = SimpleDocTemplate(output_stream)
            styles = getSampleStyleSheet()

            # 🔥 SMART PARAGRAPH FIX
            lines = text.split("\n")
            story = []
            buffer = ""

            for line in lines:
                if line.strip() == "":
                    if buffer:
                        story.append(Paragraph(buffer.strip(), styles["Normal"]))
                        buffer = ""
                else:
                    buffer += " " + line.strip()

            if buffer:
                story.append(Paragraph(buffer.strip(), styles["Normal"]))

            doc.build(story)
            return output_stream.getvalue()

        except Exception as e:
            return f"ERROR: TXT to PDF failed - {str(e)}".encode()

    # ===== IMAGE =====
    elif file_type in ["jpg", "png", "webp"]:
        if operation not in [1, 2, 3]:
            return b"ERROR: Invalid operation for image."

        target_formats = {1: "JPEG", 2: "PNG", 3: "WEBP"}

        try:
            img = Image.open(io.BytesIO(data))

            if target_formats[operation] == "JPEG" and img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            out = io.BytesIO()
            img.save(out, format=target_formats[operation])
            return out.getvalue()

        except Exception as e:
            return f"ERROR: Image processing failed - {str(e)}".encode()

    return b"ERROR: File type could not be determined."


def handle_connection(client_sock, context):
    try:
        with context.wrap_socket(client_sock, server_side=True) as conn:

            header_raw = recv_exact(conn, protocol.HEADER_SIZE)
            if not header_raw:
                return

            header = protocol.parse_header(header_raw)

            file_data = recv_exact(conn, header["file_size"])
            if file_data is None:
                return

            if not protocol.verify_checksum(file_data, header["checksum"]):
                error_msg = b"ERROR: Integrity check failed."
                conn.sendall(struct.pack("!Q", len(error_msg)))
                conn.sendall(error_msg)
                return

            result = process_file(file_data, header["filename"], header["operation"])

            conn.sendall(struct.pack("!Q", len(result)))
            conn.sendall(result)

    except Exception as e:
        print(f"[WORKER THREAD ERROR] {e}")
    finally:
        client_sock.close()


def start_worker():
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.load_cert_chain(certfile="server.crt", keyfile="server.key")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen(25)

        print(f"[WORKER] Multi-threaded Secure Brain online on {PORT}")

        while True:
            client_sock, addr = s.accept()

            client_thread = threading.Thread(
                target=handle_connection, args=(client_sock, context)
            )
            client_thread.daemon = True
            client_thread.start()


if __name__ == "__main__":
    start_worker()
