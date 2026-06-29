import os
import sys
import glob
import time
import argparse
import contextlib
from concurrent.futures import ProcessPoolExecutor, as_completed

# Import fungsi konversi murni dari skrip yang Anda buat
from segd2segy import convert_segd_to_segy

def process_single_file(input_path, output_dir):
    """
    Fungsi wrapper memproses 1 file. 
    Mengembalikan tuple (status, basename, error_message)
    """
    basename = os.path.basename(input_path)
    try:
        name_only = os.path.splitext(basename)[0]
        output_file = os.path.join(output_dir, f"{name_only}.sgy")
        
        # Membungkus stdout agar print internal dari segd2segy
        # tidak bertumpuk di layar saat diproses bersamaan.
        with open(os.devnull, 'w') as devnull:
            with contextlib.redirect_stdout(devnull):
                convert_segd_to_segy(input_path, output_file)
                
        return (True, basename, None)
    except Exception as e:
        return (False, basename, str(e))

def main():
    # 1. Setup Argumen Terminal (Dibuat opsional agar bisa fallback ke GUI)
    parser = argparse.ArgumentParser(
        description="Batch Converter SEGD ke SEGY Paralel (Super Cepat)",
        epilog="Contoh pemakaian: python batch_convert.py -i data/ -o output_final/"
    )
    parser.add_argument("-i", "--input", help="Folder (untuk banyak file) atau path ke 1 file .SEGD")
    parser.add_argument("-o", "--output", help="Folder tujuan hasil .sgy")
    parser.add_argument("-w", "--workers", type=int, default=os.cpu_count(), help="Jumlah CPU core yang dipakai (default: otomatis max core)")
    
    args = parser.parse_args()
    
    # 2. Logika GUI (Pop-up Window) jika user cuma double-click / tidak pakai argumen
    if not args.input or not args.output:
        print("Mode GUI aktif (Argumen terminal tidak lengkap)... Membuka jendela dialog.")
        try:
            import tkinter as tk
            from tkinter import filedialog, messagebox
            
            root = tk.Tk()
            root.withdraw() # Sembunyikan jendela utama
            root.attributes("-topmost", True) # Paksa pop-up muncul di paling depan
            
            messagebox.showinfo(
                "Converter SEGD ke SEGY", 
                "Selamat datang di Converter SEGD ke SEGY!\n\n"
                "Silakan ikuti 2 langkah berikut setelah klik OK:\n"
                "1. Pilih folder yang berisi file input .SEGD\n"
                "2. Pilih folder kosong untuk tempat hasil Output"
            )
            
            input_path = filedialog.askdirectory(title="LANGKAH 1: Pilih Folder Input (Berisi .SEGD)")
            if not input_path:
                print("Dibatalkan. Folder input tidak dipilih.")
                sys.exit(0)
                
            output_path = filedialog.askdirectory(title="LANGKAH 2: Pilih Folder Output Tujuan")
            if not output_path:
                print("Dibatalkan. Folder output tidak dipilih.")
                sys.exit(0)
                
            args.input = input_path
            args.output = output_path
            
        except ImportError:
            print("[!] Modul GUI (tkinter) tidak tersedia di sistem ini.")
            print("[!] Silakan jalankan via terminal menggunakan argumen: -i <folder_input> -o <folder_output>")
            sys.exit(1)
            
    # 3. Buat direktori output jika belum ada
    if not os.path.exists(args.output):
        os.makedirs(args.output)
        
    # 4. Kumpulkan file yang akan diproses
    files_to_process = []
    if os.path.isfile(args.input):
        files_to_process.append(args.input)
    elif os.path.isdir(args.input):
        # Cari file .SEGD maupun .segd secara rekursif
        files_to_process.extend(glob.glob(os.path.join(args.input, "**", "*.SEGD"), recursive=True))
        files_to_process.extend(glob.glob(os.path.join(args.input, "**", "*.segd"), recursive=True))
    else:
        print(f"[!] Error: Input '{args.input}' tidak ditemukan.")
        time.sleep(3) # Beri jeda supaya user sempat membaca error jika berjalan di jendela terpisah
        sys.exit(1)
        
    # Hilangkan path duplikat (jika ada)
    files_to_process = list(set(files_to_process))
    total_files = len(files_to_process)
    
    if total_files == 0:
        print(f"[!] Tidak ada file SEGD yang ditemukan di lokasi: {args.input}")
        time.sleep(3)
        sys.exit(0)
        
    # Tampilan UI Terminal
    print("="*60)
    print(f"🔥 Memulai Konversi Massal: {total_files} File")
    print(f"📂 Folder Input  : {args.input}")
    print(f"📂 Folder Output : {args.output}")
    print(f"🚀 Menggunakan {args.workers} core prosesor secara paralel")
    print("="*60)
    
    start_time = time.time()
    success_count = 0
    failed_files = []
    
    # 5. Pemrosesan Paralel (Multiprocessing)
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        # Submit semua tugas konversi
        futures = {executor.submit(process_single_file, f, args.output): f for f in files_to_process}
        
        completed = 0
        for future in as_completed(futures):
            completed += 1
            status, fname, err_msg = future.result()
            
            # Print progres setiap kali ada 1 file yang selesai
            if status:
                success_count += 1
                print(f"[{completed}/{total_files}] \u2705 BERHASIL: {fname}")
            else:
                failed_files.append((fname, err_msg))
                print(f"[{completed}/{total_files}] \u274c GAGAL   : {fname} ({err_msg})")
                
    elapsed = time.time() - start_time
    
    # 6. Laporan & Summary Akhir
    print("\n" + "="*60)
    print("🎉 RINGKASAN KONVERSI SELESAI 🎉")
    print("="*60)
    print(f"Waktu Total  : {elapsed:.2f} detik")
    print(f"Kecepatan    : {total_files / elapsed:.2f} file / detik")
    print(f"Berhasil     : {success_count} file")
    print(f"Gagal        : {len(failed_files)} file")
    
    # Log error agar pengguna bisa tahu file mana yang rusak
    if failed_files:
        err_path = os.path.join(args.output, "error_log.txt")
        with open(err_path, "w") as f:
            for fname, err in failed_files:
                f.write(f"{fname} -> {err}\n")
        print(f"📝 Daftar file gagal telah dicatat dan disimpan di: {err_path}")
        
    # Beri jeda 5 detik agar terminal tidak langsung tertutup otomatis (jika dijalankan via klik ganda exe)
    print("\n[Jendela ini akan tertutup otomatis dalam 5 detik...]")
    time.sleep(5)

if __name__ == "__main__":
    # Karena multiprocessing di Windows .exe butuh freeze_support
    import multiprocessing
    multiprocessing.freeze_support()
    main()
