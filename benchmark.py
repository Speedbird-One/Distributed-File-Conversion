import socket
import ssl
import struct
import os
import time
import csv
import random
import string
import numpy as np
import concurrent.futures  # Added for simultaneous requests
from PIL import Image
from reportlab.pdfgen import canvas
import matplotlib.pyplot as plt
from datetime import datetime
import protocol

# --- CONFIGURATION ---
MASTER_HOST = "127.0.0.1"
MASTER_PORT = 5000
OUTPUT_DIR = "benchmarking_files"
LOG_FILE = "comprehensive_performance.csv"

# Test Variables
TEST_SIZES = [
    1024 * 100,
    1024 * 1024,
    1024 * 1024 * 5,
    1024 * 1024 * 10,
]  # 100KB, 1MB, 5MB, 10MB
CHUNK_SIZES = [4096, 16384, 65536, 262144, 1048576]  # 4KB to 1MB
DEFAULT_CHUNK = 65536
FIXED_FILE_SIZE_FOR_CHUNK_TEST = 5 * 1024 * 1024  # 5MB
# Added concurrency levels for scaling test
CONCURRENCY_LEVELS = [1, 5, 10, 15, 20]
FIXED_FILE_SIZE_FOR_CONCURRENCY = 2 * 1024 * 1024  # 2MB for stress testing

# (Source Ext, Operation Code, Label)
CONVERSIONS = [
    (".jpg", 2, "JPG -> PNG"),
    (".jpg", 3, "JPG -> WEBP"),
    (".png", 1, "PNG -> JPG"),
    (".png", 3, "PNG -> WEBP"),
    (".webp", 1, "WEBP -> JPG"),
    (".webp", 2, "WEBP -> PNG"),
    (".txt", 4, "TXT -> PDF"),
    (".pdf", 5, "PDF -> TXT"),
]


def generate_file(ext, target_size, path):
    """Generates random content for each file type to simulate real data."""
    if ext in [".jpg", ".png", ".webp"]:
        dim = int((target_size / 2) ** 0.5)
        img_array = np.random.randint(
            0, 256, (max(32, dim), max(32, dim), 3), dtype=np.uint8
        )
        fmt = "JPEG" if ext == ".jpg" else ext[1:].upper()
        Image.fromarray(img_array).save(path, format=fmt)
    elif ext == ".txt":
        content = "".join(
            random.choice(string.ascii_letters + " \n") for _ in range(target_size)
        )
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    elif ext == ".pdf":
        c = canvas.Canvas(path)
        c.drawString(100, 750, "Automated Benchmark PDF Content " * 5)
        c.save()

    curr = os.path.getsize(path)
    if curr < target_size:
        with open(path, "ab") as f:
            f.write(b"\0" * (target_size - curr))


def run_test_iteration(filepath, op, chunk_size):
    """Measures the end-to-end throughput of a single conversion job."""
    file_size = os.path.getsize(filepath)
    header = protocol.build_header(filepath, op)
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            secure_sock = context.wrap_socket(sock, server_hostname=MASTER_HOST)
            secure_sock.settimeout(30)
            secure_sock.connect((MASTER_HOST, MASTER_PORT))

            start = time.perf_counter()
            secure_sock.sendall(header)
            with open(filepath, "rb") as f:
                while chunk := f.read(chunk_size):
                    secure_sock.sendall(chunk)

            size_raw = b""
            while len(size_raw) < 8:
                p = secure_sock.recv(8 - len(size_raw))
                if not p:
                    break
                size_raw += p

            resp_size = struct.unpack("!Q", size_raw)[0]
            received = 0
            while received < resp_size:
                p = secure_sock.recv(min(chunk_size, resp_size - received))
                if not p:
                    break
                received += len(p)

            elapsed = time.perf_counter() - start
            return (file_size / (1024 * 1024)) / elapsed  # MB/s
    except:
        return None


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(".\\performance_graphs", exist_ok=True)
    results = []

    # 1. TEST SIZE VARIATION
    print("Running File Size Benchmarks...")
    for ext, op, label in CONVERSIONS:
        for size in TEST_SIZES:
            path = os.path.join(OUTPUT_DIR, f"tmp{ext}")
            generate_file(ext, size, path)
            throughput = run_test_iteration(path, op, DEFAULT_CHUNK)
            if throughput:
                results.append(
                    {
                        "type": "size",
                        "label": label,
                        "x": size / (1024 * 1024),
                        "y": throughput,
                    }
                )

    # 2. TEST CHUNK VARIATION
    print("Running Chunk Size Benchmarks...")
    for ext, op, label in CONVERSIONS:
        path = os.path.join(OUTPUT_DIR, f"tmp_chunk{ext}")
        generate_file(ext, FIXED_FILE_SIZE_FOR_CHUNK_TEST, path)
        for c_size in CHUNK_SIZES:
            throughput = run_test_iteration(path, op, c_size)
            if throughput:
                results.append(
                    {
                        "type": "chunk",
                        "label": label,
                        "x": c_size / 1024,
                        "y": throughput,
                    }
                )

    # 3. TEST CONCURRENCY SCALING (New Section)
    print("Running Concurrency Scaling Benchmarks (up to 20 requests)...")
    for ext, op, label in CONVERSIONS:
        path = os.path.join(OUTPUT_DIR, f"tmp_concur{ext}")
        generate_file(ext, FIXED_FILE_SIZE_FOR_CONCURRENCY, path)
        for num_requests in CONCURRENCY_LEVELS:
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=num_requests
            ) as executor:
                start_batch = time.perf_counter()
                # Launch N simultaneous requests
                futures = [
                    executor.submit(run_test_iteration, path, op, DEFAULT_CHUNK)
                    for _ in range(num_requests)
                ]
                concurrent.futures.wait(futures)
                end_batch = time.perf_counter()

            total_time = end_batch - start_batch
            total_mb = (FIXED_FILE_SIZE_FOR_CONCURRENCY * num_requests) / (1024 * 1024)
            agg_throughput = total_mb / total_time  # Aggregate MB/s

            results.append(
                {
                    "type": "concurrency",
                    "label": label,
                    "x": num_requests,
                    "y": agg_throughput,
                }
            )

    # 3. VISUALIZATION
    # Plot 1: Size vs Throughput
    plt.clf()
    for label in [c[2] for c in CONVERSIONS]:
        data = [r for r in results if r["type"] == "size" and r["label"] == label]
        plt.plot(
            [d["x"] for d in data], [d["y"] for d in data], marker="o", label=label
        )
    plt.title("File Size vs Throughput (at 64KB Chunk)")
    plt.xlabel("File Size (MB)")
    plt.ylabel("Throughput (MB/s)")
    plt.legend(bbox_to_anchor=(1.05, 1), loc="upper left")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(".\\performance_graphs\\analysis_size_vs_throughput.png")

    # Plot 2: Chunk Size vs Throughput
    plt.clf()
    for label in [c[2] for c in CONVERSIONS]:
        data = [r for r in results if r["type"] == "chunk" and r["label"] == label]
        plt.plot(
            [d["x"] for d in data], [d["y"] for d in data], marker="s", label=label
        )
    plt.title(
        f"Chunk Size vs Throughput (on {FIXED_FILE_SIZE_FOR_CHUNK_TEST/(1024*1024)}MB File)"
    )
    plt.xlabel("Chunk Size (KB)")
    plt.ylabel("Throughput (MB/s)")
    plt.legend(bbox_to_anchor=(1.05, 1), loc="upper left")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(".\\performance_graphs\\analysis_chunk_vs_throughput.png")

    # Plot 3: Concurrency vs Aggregate Throughput
    plt.clf()
    for label in [c[2] for c in CONVERSIONS]:
        data = [
            r for r in results if r["type"] == "concurrency" and r["label"] == label
        ]
        plt.plot(
            [d["x"] for d in data], [d["y"] for d in data], marker="D", label=label
        )
    plt.title("Scaling: Concurrent Requests vs Aggregate Throughput")
    plt.xlabel("Number of Concurrent Requests")
    plt.ylabel("Aggregate Throughput (MB/s)")
    plt.legend(bbox_to_anchor=(1.05, 1), loc="upper left")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(".\\performance_graphs\\analysis_concurrency_scaling.png")


if __name__ == "__main__":
    main()
