import struct
import sys
import os
import re

def create_ebcdic_header(ascii_text):
    # Buat 3200 byte spasi EBCDIC (0x40)
    ebcdic = bytearray(b'\x40' * 3200)
    
    # Bersihkan teks ASCII dari null bytes
    clean_text = ''.join([chr(b) if 32 <= b <= 126 else ' ' for b in ascii_text])
    clean_text = ' '.join(clean_text.split()) # Hapus spasi berlebih
    
    # Masukkan info ekstraksi ke baris pertama Text Header
    info_str = f"C 1 CONVERTED FROM SEGD. META: {clean_text[:300]}"
    
    try:
        encoded = info_str.encode('cp500') # Encode ke EBCDIC
        ebcdic[:len(encoded)] = encoded
    except:
        pass
    return ebcdic

def convert_segd_to_segy(input_file, output_file, offset=6048, num_traces=504, ns=4096, dt=2000):
    print(f"Membaca {input_file} (Mengekstrak format 8015 mentah)...")
    
    with open(input_file, 'rb') as f_in, open(output_file, 'wb') as f_out:
        # Ekstrak Metadata dari 2048 byte pertama SEGD
        raw_header = f_in.read(2048)
        ascii_text = [b for b in raw_header if 32 <= b <= 126]
        
        # Ekstrak Koordinat & FFID dengan Regex
        text_str = ''.join(chr(b) for b in ascii_text)
        ffid = 1
        easting = 0
        northing = 0
        
        match_ev = re.search(r'EV:\s*([0-9]+)', text_str)
        if match_ev: ffid = int(match_ev.group(1))
        
        match_coord = re.search(r'E:\s*([0-9.]+)\s*N:\s*([0-9.]+)', text_str)
        if match_coord:
            easting = int(float(match_coord.group(1)) * 10)
            northing = int(float(match_coord.group(2)) * 10)
            
        hour = 0; minute = 0; second = 0
        match_time = re.search(r'([0-9]{2}):([0-9]{2}):([0-9]{2})\s*EV:', text_str)
        if match_time:
            hour = int(match_time.group(1))
            minute = int(match_time.group(2))
            second = int(match_time.group(3))
            
        # 1. Tulis 3200-byte Text Header (EBCDIC format)
        f_out.write(create_ebcdic_header(raw_header[352:1500]))
        
        # 2. Tulis 400-byte Binary Header
        bin_hdr = bytearray(400)
        struct.pack_into('>i', bin_hdr, 0, 1)      # Job ID
        struct.pack_into('>i', bin_hdr, 8, ffid)   # Line / FFID
        struct.pack_into('>h', bin_hdr, 16, dt)    
        struct.pack_into('>h', bin_hdr, 20, ns)    
        struct.pack_into('>h', bin_hdr, 24, 5)     # 5 = IEEE Float
        f_out.write(bin_hdr)

        # Lewati header teks yang kacau (6048 byte)
        f_in.seek(offset)
        
        for t in range(num_traces):
            # Baca 20 byte Trace Header
            tr_hdr = f_in.read(20)
            if len(tr_hdr) < 20:
                break
                
            # Parse trace number
            tracl = struct.unpack('>H', tr_hdr[4:6])[0]
            if tracl == 0:
                tracl = t + 1
            
            # Buat 240 byte SEG-Y trace header
            segy_hdr = bytearray(240)
            struct.pack_into('>i', segy_hdr, 0, t+1) # Trace seq dalam baris (byte 1-4)
            struct.pack_into('>i', segy_hdr, 4, tracl) # Trace seq dalam reel (byte 5-8)
            struct.pack_into('>i', segy_hdr, 8, ffid) # Field Record / Shot Point Number (byte 9-12)
            struct.pack_into('>i', segy_hdr, 12, tracl) # Trace num within record / **Channel Number** (byte 13-16)
            struct.pack_into('>i', segy_hdr, 16, ffid) # Energy Source Point (sering disamakan dgn Shot/FFID) (byte 17-20)
            struct.pack_into('>i', segy_hdr, 24, tracl) # Trace number within ensemble (sering dibaca sbg Channel) (byte 25-28)
            
            struct.pack_into('>h', segy_hdr, 28, 1) # Trace ID (1 = Seismic Data)
            
            # Koordinat X dan Y (Easting / Northing)
            struct.pack_into('>h', segy_hdr, 70, -10) # Scalar multiplier (bagi 10 karena kita kali 10 sebelumnya)
            struct.pack_into('>i', segy_hdr, 72, easting)  # Source X
            struct.pack_into('>i', segy_hdr, 76, northing) # Source Y
            struct.pack_into('>i', segy_hdr, 80, easting)  # Receiver X
            struct.pack_into('>i', segy_hdr, 84, northing) # Receiver Y
            
            struct.pack_into('>h', segy_hdr, 88, 1)    # Coordinate units (1 = Length/meters)
            
            struct.pack_into('>h', segy_hdr, 114, ns)  # Samples
            struct.pack_into('>h', segy_hdr, 116, dt)  # Interval
            
            # Waktu Perekaman (Recording Time)
            struct.pack_into('>h', segy_hdr, 156, 1999) # Tahun (dari string 99/01/08)
            struct.pack_into('>h', segy_hdr, 158, 8)    # Hari dalam setahun (Julian day 8 = 8 Januari)
            struct.pack_into('>h', segy_hdr, 160, hour)
            struct.pack_into('>h', segy_hdr, 162, minute)
            struct.pack_into('>h', segy_hdr, 164, second)
            
            f_out.write(segy_hdr)
            
            # Baca data 20-bit format 8015 (10 byte per 4 sampel)
            data_bytes = f_in.read((ns // 4) * 10)
            if len(data_bytes) < (ns // 4) * 10:
                break
                
            # Decode 20-bit ke 32-bit IEEE float
            floats = []
            for i in range(0, len(data_bytes), 10):
                block = data_bytes[i:i+10]
                
                # Exponents (Byte 1-2)
                ex1_4 = struct.unpack('>H', block[0:2])[0]
                e1 = ((ex1_4 >> 12) & 15) - 15
                e2 = ((ex1_4 >> 8) & 15) - 15
                e3 = ((ex1_4 >> 4) & 15) - 15
                e4 = (ex1_4 & 15) - 15
                
                # Fractions (Byte 3-10) -> one's complement
                f1 = struct.unpack('>h', block[2:4])[0]
                if f1 < 0: f1 = -(~f1)
                
                f2 = struct.unpack('>h', block[4:6])[0]
                if f2 < 0: f2 = -(~f2)
                
                f3 = struct.unpack('>h', block[6:8])[0]
                if f3 < 0: f3 = -(~f3)
                
                f4 = struct.unpack('>h', block[8:10])[0]
                if f4 < 0: f4 = -(~f4)
                
                floats.extend([
                    f1 * (2.0 ** e1),
                    f2 * (2.0 ** e2),
                    f3 * (2.0 ** e3),
                    f4 * (2.0 ** e4)
                ])
                
            # Pack as 32-bit floats
            f_out.write(struct.pack(f'>{ns}f', *floats))

        print(f"Selesai! {t+1} trace berhasil dikonversi secara langsung ke {output_file} (SEG-Y Standar)")

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Penggunaan: python segd2segy.py <input.SEGD> <output.sgy>")
        sys.exit(1)
        
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    output_dir = os.path.dirname(output_file)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    convert_segd_to_segy(input_file, output_file)
