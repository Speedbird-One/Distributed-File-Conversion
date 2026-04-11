import streamlit as st
import socket
import ssl
import struct
import os
import tempfile
import protocol

# --- CONFIGURATION ---
MASTER_HOST = "127.0.0.1"
MASTER_PORT = 5000


# --- HELPER FUNCTIONS ---
def recv_exact(sock, size):
    data = b""
    while len(data) < size:
        packet = sock.recv(size - len(data))
        if not packet:
            return None
        data += packet
    return data


def process_file_via_socket(temp_path, operation):
    """Communicates with the Master Server using the logic from sender.py"""
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    header = protocol.build_header(temp_path, operation)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        secure_sock = context.wrap_socket(s, server_hostname=MASTER_HOST)
        secure_sock.settimeout(30)
        secure_sock.connect((MASTER_HOST, MASTER_PORT))

        # Send header
        secure_sock.sendall(header)

        # Send file in chunks
        with open(temp_path, "rb") as f:
            while chunk := f.read(65536):
                secure_sock.sendall(chunk)

        # Receive response size (8 bytes)
        size_bytes = recv_exact(secure_sock, 8)
        if not size_bytes:
            return None, "Error: No response size from server."

        response_size = struct.unpack("!Q", size_bytes)[0]

        # Check for error message
        # Receive result bytes
        result_data = b""
        bytes_received = 0
        while bytes_received < response_size:
            data = secure_sock.recv(min(65536, response_size - bytes_received))
            if not data:
                break
            result_data += data
            bytes_received += len(data)

        return result_data, None


# --- STREAMLIT UI ---
st.set_page_config(page_title="Distributed File Converter", page_icon="⚙️")

st.title("Secure Distributed File Converter")
st.markdown("Upload files to process them via our high-performance backend cluster.")

# 1. File Upload (Accepts Multiple)
uploaded_files = st.file_uploader(
    "Drag and drop files or click to browse", accept_multiple_files=True
)

if uploaded_files:
    st.write(f"### Tasks ({len(uploaded_files)})")

    # Operation Mapping
    EXT_MAP = {1: ".jpg", 2: ".png", 3: ".webp", 4: ".pdf", 5: ".txt"}

    # Create a container for each file
    for uploaded_file in uploaded_files:
        with st.expander(f"📄 {uploaded_file.name}", expanded=True):
            ext = os.path.splitext(uploaded_file.name)[1].lower()

            # Determine available operations and filter out the current format
            ops = {}
            if ext in [".jpg", ".jpeg", ".png", ".webp"]:
                all_image_ops = {"JPG": 1, "PNG": 2, "WEBP": 3}
                # Filter logic
                if ext in [".jpg", ".jpeg"]:
                    ops = {k: v for k, v in all_image_ops.items() if k != "JPG"}
                elif ext == ".png":
                    ops = {k: v for k, v in all_image_ops.items() if k != "PNG"}
                elif ext == ".webp":
                    ops = {k: v for k, v in all_image_ops.items() if k != "WEBP"}

            elif ext == ".txt":
                ops = {"PDF": 4}
            elif ext == ".pdf":
                ops = {"Plain Text (.txt)": 5}

            if not ops:
                st.error("Unsupported file type.")
                continue

            col1, col2 = st.columns([2, 1])
            with col1:
                selected_op_label = st.selectbox(
                    f"Select conversion for {uploaded_file.name}:",
                    options=list(ops.keys()),
                    key=f"op_{uploaded_file.name}",
                )
                op_code = ops[selected_op_label]

            with col2:
                if st.button(
                    f"Convert {uploaded_file.name}", key=f"btn_{uploaded_file.name}"
                ):
                    with st.spinner("Processing..."):
                        # Save to temp file so protocol.py can read it
                        with tempfile.NamedTemporaryFile(
                            delete=False, suffix=ext
                        ) as tmp:
                            tmp.write(uploaded_file.getvalue())
                            tmp_path = tmp.name

                        try:
                            result_data, error = process_file_via_socket(
                                tmp_path, op_code
                            )

                            if error:
                                st.error(error)
                            elif result_data.startswith(b"ERROR:"):
                                st.error(result_data.decode())
                            else:
                                # Prepare output filename
                                name_no_ext = os.path.splitext(uploaded_file.name)[0]
                                new_ext = EXT_MAP.get(op_code, ".bin")
                                output_name = f"converted_{name_no_ext}{new_ext}"

                                st.success(f"Conversion Complete!")
                                st.download_button(
                                    label="Download Result",
                                    data=result_data,
                                    file_name=output_name,
                                    mime="application/octet-stream",
                                )
                        finally:
                            if os.path.exists(tmp_path):
                                os.remove(tmp_path)
