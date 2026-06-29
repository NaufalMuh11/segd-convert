import os
import sys
import glob
import time
import argparse
import contextlib
from concurrent.futures import ProcessPoolExecutor, as_completed

# Import pure conversion function from user's script
from segd2segy import convert_segd_to_segy

def process_single_file(input_path, output_dir):
    """
    Wrapper function to process a single file. 
    Returns a tuple: (status, basename, error_message)
    """
    basename = os.path.basename(input_path)
    try:
        name_only = os.path.splitext(basename)[0]
        output_file = os.path.join(output_dir, f"{name_only}.sgy")
        
        # Wrap stdout to prevent segd2segy internal prints 
        # from cluttering the screen during multiprocessing.
        with open(os.devnull, 'w') as devnull:
            with contextlib.redirect_stdout(devnull):
                convert_segd_to_segy(input_path, output_file)
                
        return (True, basename, None)
    except Exception as e:
        return (False, basename, str(e))

def main():
    # 1. Setup Terminal Arguments (Optional to fallback to GUI)
    parser = argparse.ArgumentParser(
        description="Parallel Batch SEGD to SEGY Converter",
        epilog="Example: python batch_convert.py -i data/ -o output_final/"
    )
    parser.add_argument("-i", "--input", help="Directory (for multiple files) or path to a single .SEGD file")
    parser.add_argument("-o", "--output", help="Output directory for .sgy results")
    parser.add_argument("-w", "--workers", type=int, default=os.cpu_count(), help="Number of CPU cores to use (default: max available cores)")
    
    args = parser.parse_args()
    
    # 2. GUI Logic (Pop-up Window) if run without arguments
    if not args.input or not args.output:
        print("GUI mode activated (Missing CLI arguments)... Opening dialog window.")
        try:
            import tkinter as tk
            from tkinter import filedialog, messagebox
            
            root = tk.Tk()
            root.withdraw() # Hide the main window
            root.attributes("-topmost", True) # Force pop-up to the front
            
            messagebox.showinfo(
                "SEGD to SEGY Converter", 
                "Welcome to the SEGD to SEGY Converter!\n\n"
                "Please follow these 2 steps after clicking OK:\n"
                "1. Select the input folder containing .SEGD files.\n"
                "2. Select an empty output folder for the results."
            )
            
            input_path = filedialog.askdirectory(title="STEP 1: Select Input Folder (.SEGD)")
            if not input_path:
                print("Cancelled. No input folder selected.")
                sys.exit(0)
                
            output_path = filedialog.askdirectory(title="STEP 2: Select Output Folder")
            if not output_path:
                print("Cancelled. No output folder selected.")
                sys.exit(0)
                
            args.input = input_path
            args.output = output_path
            
        except ImportError:
            print("[!] GUI module (tkinter) is not available on this system.")
            print("[!] Please run via terminal using arguments: -i <input_folder> -o <output_folder>")
            sys.exit(1)
            
    # 3. Create output directory if it doesn't exist
    if not os.path.exists(args.output):
        os.makedirs(args.output)
        
    # 4. Collect files to process
    files_to_process = []
    if os.path.isfile(args.input):
        files_to_process.append(args.input)
    elif os.path.isdir(args.input):
        # Search for .SEGD and .segd files recursively
        files_to_process.extend(glob.glob(os.path.join(args.input, "**", "*.SEGD"), recursive=True))
        files_to_process.extend(glob.glob(os.path.join(args.input, "**", "*.segd"), recursive=True))
    else:
        print(f"[!] Error: Input '{args.input}' not found.")
        time.sleep(3) # Pause so users can read the error if run in a separate window
        sys.exit(1)
        
    # Remove duplicates (if any)
    files_to_process = list(set(files_to_process))
    total_files = len(files_to_process)
    
    if total_files == 0:
        print(f"[!] No SEGD files found in: {args.input}")
        time.sleep(3)
        sys.exit(0)
        
    # Terminal UI Display
    print("="*60)
    print(f"🔥 Starting Batch Conversion: {total_files} Files")
    print(f"📂 Input Folder  : {args.input}")
    print(f"📂 Output Folder : {args.output}")
    print(f"🚀 Using {args.workers} processor cores in parallel")
    print("="*60)
    
    start_time = time.time()
    success_count = 0
    failed_files = []
    
    # 5. Parallel Processing (Multiprocessing)
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        # Submit all conversion tasks
        futures = {executor.submit(process_single_file, f, args.output): f for f in files_to_process}
        
        completed = 0
        for future in as_completed(futures):
            completed += 1
            status, fname, err_msg = future.result()
            
            # Print progress as each file completes
            if status:
                success_count += 1
                print(f"[{completed}/{total_files}] \u2705 SUCCESS: {fname}")
            else:
                failed_files.append((fname, err_msg))
                print(f"[{completed}/{total_files}] \u274c FAILED : {fname} ({err_msg})")
                
    elapsed = time.time() - start_time
    
    # 6. Final Summary & Report
    print("\n" + "="*60)
    print("🎉 CONVERSION SUMMARY 🎉")
    print("="*60)
    print(f"Total Time  : {elapsed:.2f} seconds")
    print(f"Speed       : {total_files / elapsed:.2f} files/second")
    print(f"Success     : {success_count} files")
    print(f"Failed      : {len(failed_files)} files")
    
    # Log errors so users know which files are corrupted
    if failed_files:
        err_path = os.path.join(args.output, "error_log.txt")
        with open(err_path, "w") as f:
            for fname, err in failed_files:
                f.write(f"{fname} -> {err}\n")
        print(f"📝 List of failed files has been saved to: {err_path}")
        
    # Pause for 5 seconds so the terminal doesn't close immediately (if run via double-click)
    print("\n[This window will close automatically in 5 seconds...]")
    time.sleep(5)

if __name__ == "__main__":
    # Required for multiprocessing in Windows .exe
    import multiprocessing
    multiprocessing.freeze_support()
    main()
