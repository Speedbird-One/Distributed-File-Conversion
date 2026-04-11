import struct
import hashlib
import os

HEADER_FORMAT = "!4s32s16s30sQI"
HEADER_SIZE = 94

EXPECTED_AUTH_TOKEN = "super_secret_token_123456789012"
SUPPORTED_VERSION = "v1.0"
# Ensure all operations are included here
SUPPORTED_OPERATIONS = {1, 2, 3, 4, 5}

def calculate_checksum(filepath):
    md5 = hashlib.md5()
    with open(filepath, 'rb') as f:
        while chunk := f.read(4096):
            md5.update(chunk)
    return md5.digest()

def build_header(filepath, operation, auth_token=b"super_secret_token_123456789012"):
    version = b"v1.0"
    token_bytes = auth_token.ljust(32, b'\x00')[:32]
    checksum = calculate_checksum(filepath)
    filename = os.path.basename(filepath).encode('utf-8')[:30].ljust(30, b'\x00')
    file_size = os.path.getsize(filepath)
    return struct.pack(HEADER_FORMAT, version, token_bytes, checksum, filename, file_size, operation)

def parse_header(raw_header):
    unpacked = struct.unpack(HEADER_FORMAT, raw_header)
    return {
        "version": unpacked[0].decode('utf-8', errors='ignore').strip('\x00'),
        "auth_token": unpacked[1].decode('utf-8', errors='ignore').strip('\x00'),
        "checksum": unpacked[2], 
        "filename": unpacked[3].decode('utf-8', errors='ignore').strip('\x00'),
        "file_size": unpacked[4],
        "operation": unpacked[5]
    }

def verify_checksum(file_data, expected_checksum):
    return hashlib.md5(file_data).digest() == expected_checksum

def validate_auth_token(token):
    return token == EXPECTED_AUTH_TOKEN

def validate_version(version):
    return version == SUPPORTED_VERSION

def validate_operation(operation):
    return operation in SUPPORTED_OPERATIONS