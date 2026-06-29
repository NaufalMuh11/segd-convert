# SEGD to SEG-Y Converter (Fairfield / SeisUnix)

Repositori ini menyediakan seperangkat alat untuk mengonversi data seismik mentah berformat **SEG-D (Fairfield Nodal/ZNode)** menjadi format **SEG-Y Standar (Big-Endian)**. 

Ada beberapa metode konversi yang tersedia di dalam proyek ini, baik yang menggunakan skrip Python murni (100% akurat) maupun kombinasi Docker (SeisUnix) dengan perbaikan Python.

## 📂 Struktur Folder
- `data/` : Tempat untuk meletakkan file input `.SEGD` yang ingin diproses.
- `output/` : Folder output sementara (misalnya untuk file `.su`).
- `output_final/` : Folder output akhir untuk file `.sgy`.
- `segdread.c` & `Dockerfile.segdread` : Source code dan Dockerfile untuk membuat image khusus `segdread` dari SeisUnix.
- `su2segy.py`, `segd2segy.py`, `convert_fairfield.py` : Kumpulan skrip Python untuk memproses data byte.

---

## ⚙️ Persyaratan Sistem
- **Python 3.x** (Untuk menjalankan skrip Python secara lokal).
- **Docker Desktop** (Jika menggunakan metode SeisUnix atau Docker-Compose).
- **PowerShell** (Untuk menjalankan skrip otomasi `.ps1` di Windows).

---

## 🚀 Cara Menjalankan Program

Pindahkan semua file seismik `.SEGD` yang ingin Anda konversi ke dalam folder `data/` sebelum menjalankan metode di bawah ini.

### Metode 1: Menggunakan Skrip Pure Python (Direkomendasikan)
Metode ini sangat akurat, berjalan secara lokal (tanpa Docker), dan langsung mengonversi SEG-D ke SEG-Y tanpa file perantara.
1. Buka PowerShell.
2. Jalankan skrip:
   ```powershell
   .\process_all_pure.ps1
   ```
3. Hasil konversi (`.sgy`) akan tersedia di folder `output_final/`.

### Metode 2: Menggunakan SeisUnix (Docker) & Python
Metode ini menggunakan program `segdread` dari SeisUnix yang di-containerize dengan Docker (memproses file ke format SU Little-Endian), lalu diperbaiki format dan endianness-nya menggunakan skrip Python.
1. Pastikan Docker Desktop sedang berjalan.
2. Build image Docker untuk `segdread` (Hanya perlu dilakukan sekali pertama kali):
   ```bash
   docker build -f Dockerfile.segdread -t segdread:latest .
   ```
3. Jalankan skrip PowerShell:
   ```powershell
   .\process_all.ps1
   ```
4. Hasil antara `.su` akan ada di `output/` dan file akhir `.sgy` akan ada di `output_final/`.

### Metode 3: Menggunakan Docker Compose (Fully Containerized)
Metode ini menggunakan skrip Python yang berjalan penuh di dalam Docker, cocok jika Anda tidak memiliki Python di komputer lokal.
1. Pastikan Docker Desktop sedang berjalan.
2. Jalankan perintah berikut di terminal/PowerShell:
   ```bash
   docker-compose up --build
   ```
3. Proses konversi akan berjalan dan hasil akhirnya (file `.sgy`) akan muncul di folder `output/`.

---

## 📝 Catatan Penting
- Format akhir SEG-Y sudah disesuaikan menjadi **Big-Endian** agar dapat terbaca standar di software analisis seismik.
- Trace dan sampel bisa di-trim/dipotong untuk memenuhi batas sampel tertentu (sesuai konfigurasi di dalam file python terkait seperti `su2segy.py`).
