# SEGD to SEG-Y Batch Converter

A standalone, high-performance utility designed to convert raw **SEG-D** seismic data into the standard **SEG-Y (Big-Endian)** format. Engineered for speed and reliability, this tool utilizes Python's multiprocessing capabilities to execute batch conversions across thousands of files simultaneously.

## Key Features

- **High-Performance Multiprocessing**: Automatically scales to utilize all available CPU cores, minimizing processing time for massive datasets.
- **Graphical User Interface (GUI)**: Includes a compiled Windows executable (`.exe`) with a native folder-selection dialog for seamless, no-code operation.
- **Fault-Tolerant Execution**: Corrupted or malformed files will not interrupt the batch process. Errors are securely logged to `error_log.txt` for post-process review.
- **Recursive Directory Parsing**: Automatically discovers and processes all `.SEGD` files nested within the input directory tree.
- **Zero Dependencies**: Pure Python implementation with no reliance on Docker, WSL, or legacy SeisUnix installations.

---

## Installation

### Option 1: Standalone Executable (Recommended)
No Python installation or programming experience is required.

1. Navigate to the **Releases** section of this repository (or download the source code as a ZIP archive).
2. Extract the archive and locate the `dist/batch_convert.exe` binary.
3. The executable is ready to use immediately on any Windows environment.

### Option 2: Source Code (For Developers)
To run the source code or build the executable manually:

```bash
git clone https://github.com/NaufalMuh11/segd-shifter.git
cd segd-shifter
```
*(Requires Python 3.8+)*

---

## Usage Guide

### Graphical Mode (Interactive)
1. Double-click the `batch_convert.exe` binary.
2. Follow the prompt to select the **Input Directory** containing the raw `.SEGD` files.
3. Select an empty **Output Directory** to store the processed `.sgy` files.
4. The conversion will execute automatically, displaying real-time progress in the terminal window.

### Command-Line Interface (CLI)
For headless operation or integration into automated pipelines, run the script via terminal:

```bash
python batch_convert.py --input <path_to_input_dir> --output <path_to_output_dir>
```

**Optional Arguments:**
- `-w`, `--workers`: Explicitly define the number of concurrent processes (e.g., `-w 8`). Defaults to maximum available logical cores.

---

## Architecture Overview
- `batch_convert.py`: The entry point orchestrating CLI/GUI routing and parallel task distribution.
- `segd2segy.py`: The core parsing engine executing the byte-level translation to IEEE Float.
- `dist/batch_convert.exe`: The packaged release binary compiled via PyInstaller.
