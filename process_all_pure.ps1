# process_all_pure.ps1
# Script untuk memproses semua file SEGD menjadi SEG-Y Standar menggunakan Pure Python

New-Item -ItemType Directory -Force -Path output_final | Out-Null

$segd_files = Get-ChildItem -Path data -Filter *.SEGD

foreach ($file in $segd_files) {
    $basename = $file.BaseName
    
    Write-Host "========================================"
    Write-Host "Memproses file: $($file.Name) dengan metode 100% akurat"
    Write-Host "========================================"
    
    python segd2segy.py "data/$($file.Name)" "output_final/$basename.sgy"
    
    if ($?) {
        Write-Host "Selesai memproses: $basename.sgy`n" -ForegroundColor Green
    } else {
        Write-Host "ERROR: Gagal memproses $($file.Name).`n" -ForegroundColor Red
    }
}

Write-Host "Semua file telah selesai diproses!" -ForegroundColor Cyan
