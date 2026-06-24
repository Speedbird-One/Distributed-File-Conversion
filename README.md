# Distributed File Conversion Service

## Overview
The project is a high-performance, three-tier distributed system designed for secure file conversion. Built using low-level TCP socket programming and wrapped in TLS encryption, it enables users to transform files (Images, PDFs, Text) across a network without local processing overhead on the client side.

The system utilizes a dedicated Master-Worker architecture to ensure scalability and security, providing both a web-based UI and a headless CLI for various environment needs.

## System Architecture
The system is divided into three distinct layers to decouple the user interface from the processing logic:

* **Client Layer:**
    * `app.py`: A Streamlit-based web interface for intuitive drag-and-drop file operations.

    * `sender.py`: A CLI-based alternative for headless or automated environments.

* **Orchestration Layer (Master):**

    * `master.py`: Acts as a multi-threaded TLS proxy that listens on port 5000.

    * It validates authentication headers and tunnels data to the worker layer without saving files locally to ensure privacy and speed.

* **Processing Layer (Worker):**

    * `worker.py`: The engine of the system which uses Magic Numbers for file-type detection.

    * It performs conversions (via Pillow, ReportLab, and PyPDF2) entirely in-memory using io.BytesIO.

* **Utility & Protocol:**

    * `protocol.py`: Defines the 94-byte fixed-length header using Python's struct module.

    * `benchmark.py`: A tool for automated load testing across various file sizes, chunk sizes, and concurrency levels.

## Protocol Specification
To ensure cross-platform compatibility, the system uses a 94-byte Big-Endian packed binary structure.

| Offset | Field | Size | Description |
|--------|-------|------|-------------|
| 0 | Version | 4B | Protocol version (e.g., v1.0) |
| 4	| Auth Token | 32B | Padded string for authentication |
| 36 | Checksum | 16B | MD5 hash of file body for integrity |
| 52 | Filename | 30B | Padded original filename |
| 82 | File Size | 8B | Unsigned 64-bit integer |
| 90 | Operation | 4B | Conversion ID (Types 1–5) |

## How to Run 
**Prerequisites**
Ensure you have Python 3.x installed. It is recommended to use a virtual environment.

### Installation
1. Install the required modules:
    ```bash
    pip install -r requirements.txt
    ```

### Execution
1. **Initialize the Backend:** Start the Master and Worker services.
    ```bash
    python backend_init.py
    ```

2. **Launch the Interface:** Open the Streamlit dashboard.
    ```bash
    streamlit run app.py
    ```

## Performance Analysis & Conclusions
The visualizations supporting the following conclusions can be found in the `./performance_graphs` directory of this repository.

1. **The 64KB Buffer Sweet Spot**
Throughput increases exponentially as chunk sizes move from 4KB to 64KB. Beyond 64KB, performance plateaus, indicating it is the optimal buffer size to minimize system call overhead without over-saturating the network.

2. **Operation Bottlenecks**
    * **Network-Bound:** Fast operations like PNG to JPG conversion peak at over 15 MB/s, where the primary bottleneck is the network pipe.

    * **CPU-Bound:** TXT to PDF conversion remains nearly flat near zero. The ReportLab layout engine is so intensive that network speed becomes irrelevant.

3. **Scalability through Multithreading**
The system demonstrates successful parallelization across CPU cores. Aggregate throughput for JPG to PNG conversions jumped from ~6 MB/s with 1 client to over 25 MB/s with 20 clients.

4. **Memory and TLS Overhead**
    * **Warm-up Latency:** Small files (under 100KB) suffer from TLS handshake and header parsing overhead.

    * **Memory Peak:** Performance peaks at 1MB file sizes. Files over 1MB hit memory management limits such as Python’s garbage collection and buffer reallocations.
