# process_all.ps1
# Script untuk memproses semua file SEGD menjadi SEG-Y Standar

# 1. Pastikan folder output ada
New-Item -ItemType Directory -Force -Path output | Out-Null
New-Item -ItemType Directory -Force -Path output_final | Out-Null

# 2. Dapatkan semua file SEGD di folder data
$segd_files = Get-ChildItem -Path data -Filter *.SEGD

foreach ($file in $segd_files) {
    $basename = $file.BaseName
    
    Write-Host "========================================"
    Write-Host "Memproses file: $($file.Name)"
    Write-Host "========================================"
    
    # Langkah 1: Ekstrak SEGD ke SU menggunakan Docker
    Write-Host "Langkah 1: Konversi SEGD -> SU (Little-Endian)"
    
    # Perintah Docker (pastikan docker desktop berjalan)
    $docker_cmd = "segdread tape=/data/$($file.Name) fairfield=1 verbose=0 > /output/$basename.su"
    
    docker run --rm `
        -v "$pwd/data:/data" `
        -v "$pwd/output:/output" `
        --entrypoint sh `
        segdread:latest `
        -c $docker_cmd
    
    # Langkah 2: Rapikan dari SU ke Standar SEG-Y (Big-Endian) dengan Python
    if (Test-Path "output/$basename.su") {
        Write-Host "Langkah 2: Konversi SU -> SEG-Y Standar (Big-Endian)"
        python su2segy.py "output/$basename.su" "output_final/$basename.sgy"
        
        Write-Host "Selesai memproses: $basename.sgy`n"
    } else {
        Write-Host "ERROR: Gagal memproses $($file.Name) pada tahap pertama.`n" -ForegroundColor Red
    }
}

Write-Host "Semua file telah selesai diproses!" -ForegroundColor Green
Write-Host "File final SEG-Y ada di folder: output_final\" -ForegroundColor Green
