import struct
import sys
import os

def convert_su_to_segy(input_file, output_file):
    print(f"Membaca {input_file} (Format SU)...")
    with open(input_file, 'rb') as f_in, open(output_file, 'wb') as f_out:
        # 1. Tulis 3200-byte Text Header (ASCII spasi)
        f_out.write(b' ' * 3200)
        
        # 2. Ambil ns dan dt
        trace_header = f_in.read(240)
        if not trace_header:
            print("File kosong!")
            return
            
        ns = struct.unpack('<h', trace_header[114:116])[0]
        dt = struct.unpack('<h', trace_header[116:118])[0]
        
        target_ns = 4092
        print(f"Memotong sampel dari {ns} menjadi {target_ns} sampel...")
        
        # 3. Tulis 400-byte Binary Header
        bin_hdr = bytearray(400)
        struct.pack_into('>h', bin_hdr, 16, dt)    
        struct.pack_into('>h', bin_hdr, 20, target_ns)  # Set ke 4092
        struct.pack_into('>h', bin_hdr, 24, 5)     # 5 = IEEE Float
        f_out.write(bin_hdr)

        # 4. Konversi Trace
        f_in.seek(0)
        trace_count = 0
        while True:
            hdr = f_in.read(240)
            if len(hdr) < 240:
                break
            data = f_in.read(ns * 4)
            if len(data) < ns * 4:
                break
            
            new_hdr = bytearray(hdr)
            
            # Perbaiki Endianness Field Penting Standar SEG-Y
            tracl = struct.unpack('<i', hdr[0:4])[0]
            trid = struct.unpack('<h', hdr[28:30])[0]
            delrt = struct.unpack('<h', hdr[108:110])[0]
            
            struct.pack_into('>i', new_hdr, 0, tracl) # Trace seq (byte 1)
            struct.pack_into('>i', new_hdr, 4, tracl) # Trace seq (byte 5)
            struct.pack_into('>h', new_hdr, 28, trid) # Trace ID (1 = Seismic Data)
            struct.pack_into('>h', new_hdr, 108, delrt) # Delay Recording Time
            struct.pack_into('>h', new_hdr, 114, target_ns)  # Update ke 4092
            struct.pack_into('>h', new_hdr, 116, dt)  # Interval
            
            f_out.write(new_hdr)
            
            # Ubah data dari Float Little-Endian ke Big-Endian dan potong jadi 4092
            floats = struct.unpack(f'<{ns}f', data)
            floats_cut = floats[:target_ns] # Ambil persis 4092 sampel
            f_out.write(struct.pack(f'>{target_ns}f', *floats_cut))
            
            trace_count += 1

        print(f"Selesai! {trace_count} trace berhasil dikonversi ke {output_file} (SEG-Y Standar, {target_ns} sampel)")

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Penggunaan: python su2segy.py <input.su> <output.sgy>")
        sys.exit(1)
        
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    # Buat direktori output final jika belum ada
    output_dir = os.path.dirname(output_file)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    convert_su_to_segy(input_file, output_file)
