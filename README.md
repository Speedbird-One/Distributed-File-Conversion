## Inferences from Performance Graphs

### 1. The 64KB Sweet Spot (Network Efficiency)
Throughput skyrockets from 4KB to 64KB chunk size but plateaus after that. 
64KB is the optimal buffer size — anything smaller causes too much overhead 
from frequent system calls, anything larger doesn't help because the network 
pipe is already saturated.

### 2. CPU-Bound vs Network-Bound Operations
PNG to JPG conversion peaks at over 15 MB/s (network-bound — fast operation, 
bottleneck is the network). TXT to PDF is nearly flat near zero (CPU-bound — 
ReportLab's layout engine is so intensive that network speed is irrelevant).

### 3. Proof of Multithreading
Aggregate throughput climbs significantly with concurrent requests — JPG to PNG 
jumps from ~6 MB/s with 1 client to over 25 MB/s with 20 clients. If the server 
was single-threaded, aggregate speed would stay flat. Because it increases, the 
system is successfully parallelizing across multiple CPU cores.

### 4. The 1MB Performance Peak (Memory Cache Effects)
Most operations perform best at 1MB before declining toward 10MB. Files under 
100KB suffer from TLS handshake and header warm-up overhead. Files over 1MB 
hit memory management limits like Python garbage collection and buffer 
reallocations.

---

## Summary

| Metric | Observation | Conclusion |
|--------|-------------|------------|
| Optimal Buffer | Performance plateaus at 64KB | Minimizes system call overhead |
| Scalability | 20 clients = 4x higher aggregate speed | Multi-threading is working |
| Bottleneck | TXT to PDF is consistently slowest | CPU-bound processing is the primary limit |

---

## Architecture

Three-tier distributed system using low-level TCP sockets wrapped in TLS 
encryption.

- **protocol.py** — Defines the 94-byte fixed-length header using Python's 
struct module. Handles MD5 checksums, auth token validation, and operation 
codes (1–5).
- **master.py** — Multi-threaded TLS proxy. Listens on port 5000, establishes 
a secondary tunnel to the worker on port 6000. Validates headers before piping 
binary data to the worker without saving locally.
- **worker.py** — Multi-threaded processing engine. Uses Magic Numbers to 
detect file types. Performs image transformations (Pillow), text-to-PDF 
(ReportLab), and PDF extraction (PyPDF2). Operates entirely in-memory using 
io.BytesIO.
- **app.py** — Streamlit UI for drag-and-drop browser-based uploads and 
downloads.
- **sender.py** — CLI alternative for headless environments.
- **benchmark.py** — Automates load testing across file size, chunk size, and 
concurrency axes.

---

## Protocol Header Format

94-byte Big-Endian packed binary structure for cross-platform compatibility.

| Offset | Field | Size | Description |
|--------|-------|------|-------------|
| 0 | Version | 4B | Protocol version (e.g. v1.0) |
| 4 | Auth Token | 32B | Padded string for authentication |
| 36 | Checksum | 16B | MD5 hash of file body for integrity |
| 52 | Filename | 30B | Padded original filename |
| 82 | File Size | 8B | Unsigned 64-bit integer |
| 90 | Operation | 4B | Conversion ID (1–5) |

---

## Bottlenecks Identified

- **CPU Saturation** — TXT to PDF stays near 0.5 MB/s regardless of file size 
or concurrency due to ReportLab's layout engine.
- **Memory Overhead** — Worker loads full file into BytesIO before processing. 
Twenty simultaneous 50MB requests could consume over 2GB of RAM instantly.
- **Network Handshake Latency** — Small files (100KB) show lower throughput 
because TLS handshake and header parsing take a larger percentage of total time.

---

## Future Optimizations

1. **Worker Pool** — Replace infinite thread spawning with ThreadPoolExecutor 
to prevent server crashes from too many simultaneous threads.
2. **Zero-Copy Transfers** — Use sendfile() to move data directly from disk to 
network card, bypassing application memory.
3. **Result Caching** — Return cached results for duplicate uploads detected 
via MD5 checksum.
4. **Async I/O** — Convert master.py to asyncio to handle thousands of 
concurrent connections on a single thread.
5. **Chunked Streaming** — Send converted chunks back to client as soon as 
they are processed rather than waiting for the full file.