/*
 * fairfield_segd2segy.c
 *
 * Pure C converter: Fairfield Nodal SEG-D (Z-Land/ZNode) → SEG-Y
 *
 * Self-contained, no SeisUnix/Sfio dependency.
 * Reads raw SEG-D byte stream, handles Fairfield quirk where
 * scan_type/chan_set in demux trace header are raw binary (not BCD).
 *
 * Compile: gcc -o fairfield_segd2segy fairfield_segd2segy.c -lm
 * Usage:   ./fairfield_segd2segy input.SEGD -o output.sgy [-v] [--gain] [--ns N] [--ffid N]
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <math.h>
#include <time.h>

/* ========================================================================
 * Constants
 * ======================================================================== */
#define SEGY_TXT_SIZE   3200
#define SEGY_BIN_SIZE   400
#define SEGY_TRH_SIZE   240
#define SEGD_BLOCK      32
#define DEMUX_TRH_SIZE  20

/* ========================================================================
 * Byte-order helpers (big-endian I/O)
 * ======================================================================== */
static inline uint16_t rd_be16(const uint8_t **p) {
    uint16_t v = ((uint16_t)(*p)[0]<<8)|(*p)[1]; *p += 2; return v;
}
static inline int16_t  rd_be16s(const uint8_t **p) { return (int16_t)rd_be16(p); }
static inline uint8_t  rd_u8(const uint8_t **p) { return *(*p)++; }

static inline void w_be16(uint8_t *b, int o, uint16_t v) {
    b[o]=v>>8&0xFF; b[o+1]=v&0xFF;
}
static inline void w_be32(uint8_t *b, int o, uint32_t v) {
    w_be16(b,o,v>>16); w_be16(b,o+2,v&0xFFFF);
}
static inline void w_fl32(uint8_t *b, int o, float v) {
    uint32_t u; memcpy(&u, &v, 4); w_be32(b,o,u);
}

/* ========================================================================
 * BCD: nibble-based decode from raw byte array.
 * nibble_index = byte*2 + 0(high) / 1(low)
 * ======================================================================== */
static int bcd_nibbles(const uint8_t *raw, int start_nib, int n) {
    int val = 0;
    for (int i = 0; i < n; i++) {
        int nib = start_nib + i;
        val = val * 10 + ((raw[nib/2] >> (4*(1 - (nib&1)))) & 0x0F);
    }
    return val;
}

/* ========================================================================
 * Format 8015 decoder: 10 bytes → 4 IEEE floats
 * Adapted from SeisUnix segdread.c F8015_to_float()
 * ======================================================================== */
static void decode_8015(const uint8_t *buf, float *out, int ns) {
    for (int i = 0; i < ns; i += 4) {
        uint16_t ep = (buf[0]<<8)|buf[1];
        for (int c = 0; c < 4; c++) {
            int expo = ((ep >> (4*(3-c))) & 0x0F) - 15;
            int16_t frac = (buf[2+2*c]<<8) | buf[3+2*c];
            if (i+c < ns) out[i+c] = (float)ldexp((double)frac, expo);
        }
        buf += 10;
    }
}

/* ========================================================================
 * SEG-Y writer helpers
 * ======================================================================== */
static void segy_text_header(uint8_t *buf, const char *inpath) {
    memset(buf, ' ', SEGY_TXT_SIZE);
    time_t t = time(NULL);
    struct tm *tm = localtime(&t);
    snprintf((char*)buf, SEGY_TXT_SIZE,
        "Fairfield SEG-D -> SEG-Y  Input: %s  %04d-%02d-%02d %02d:%02d:%02d",
        inpath, tm->tm_year+1900, tm->tm_mon+1, tm->tm_mday,
        tm->tm_hour, tm->tm_min, tm->tm_sec);
}

static void segy_bin_header(uint8_t *buf, int ns, int dt) {
    memset(buf, 0, SEGY_BIN_SIZE);
    w_be16(buf, 12, (uint16_t)dt);    /* sample interval μs */
    w_be16(buf, 14, (uint16_t)dt);
    w_be16(buf, 16, (uint16_t)ns);    /* samples/trace */
    w_be16(buf, 18, (uint16_t)ns);
    w_be16(buf, 20, 5);               /* data format: IEEE float */
    w_be16(buf, 46, 0x0100);          /* SEG-Y Rev 1 */
    w_be16(buf, 48, 1);               /* fixed trace length */
}

static void segy_trh(uint8_t *trh, int tracl, int fldr, int tracf, int ep,
    int trid, int ns, int dt, int delrt, int yr, int day, int h, int m, int s) {
    memset(trh, 0, SEGY_TRH_SIZE);
    w_be32(trh, 0,   (uint32_t)tracl);
    w_be32(trh, 8,   (uint32_t)fldr);
    w_be32(trh, 12,  (uint32_t)tracf);
    w_be32(trh, 16,  (uint32_t)ep);
    w_be16(trh, 28,  (uint16_t)trid);
    w_be16(trh, 108, (uint16_t)delrt);
    w_be16(trh, 114, (uint16_t)ns);
    w_be16(trh, 116, (uint16_t)dt);
    w_be16(trh, 156, (uint16_t)yr);
    w_be16(trh, 158, (uint16_t)day);
    w_be16(trh, 160, (uint16_t)h);
    w_be16(trh, 162, (uint16_t)m);
    w_be16(trh, 164, (uint16_t)s);
}

/* ========================================================================
 * Read one 32-byte SEG-D block; returns -1 on short read
 * ======================================================================== */
static int read_block(FILE *fp, uint8_t *buf) {
    return (fread(buf, 1, SEGD_BLOCK, fp) == SEGD_BLOCK) ? 0 : -1;
}

/* ========================================================================
 * Main
 * ======================================================================== */
int main(int argc, char **argv) {
    const char *inpath = NULL, *outpath = NULL;
    FILE *fin = NULL, *fout = NULL;
    int ret = 1;
    uint8_t blk[SEGD_BLOCK];

    /* Flags */
    int verbose = 0, gain_flag = 0, ns_override = 0, ffid_override = 0;

    /* ---- parse CLI ---- */
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "-o") && i+1<argc)      outpath = argv[++i];
        else if (!strcmp(argv[i], "-v"))              verbose++;
        else if (!strcmp(argv[i], "--gain"))          gain_flag = 1;
        else if (!strcmp(argv[i], "--ns") && i+1<argc) ns_override = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--ffid") && i+1<argc) ffid_override = atoi(argv[++i]);
        else if (argv[i][0] == '-') {
            fprintf(stderr,"Usage: %s input.SEGD -o output.sgy [-v] [--ns N] [--gain] [--ffid N]\n", argv[0]);
            return 1;
        } else inpath = argv[i];
    }
    if (!inpath) { fprintf(stderr,"No input file\n"); return 1; }

    fin = fopen(inpath, "rb");
    if (!fin) { perror("fopen input"); goto done; }
    fout = outpath ? fopen(outpath, "wb") : stdout;
    if (!fout) { perror("fopen output"); goto done; }

    /* ===================================================================
     * GENERAL HEADER #1 (32 bytes) — SEG-D standard layout
     *
     * Byte offsets (0-indexed):
     *   0-1:  f[0..1]         file number (4 BCD digits)
     *   2-3:  y               format code (hex)
     *   4-9:  k[0..5]         general constants K1-K12 (12 BCD)
     *   10:   yr               year (2 BCD)
     *   11:   gh_dy1           hi=n_gh, lo=day digit 1
     *   12:   dy               day digits 2-3
     *   13:   h                hour (2 BCD)
     *   14:   mi               minute (2 BCD)
     *   15:   se               second (2 BCD)
     *   16:   m[0]             manufacturer code
     *   17:   m[1]             manufacturer serial#
     *   18:   m[2]
     *   19-21: b[0..2]         bytes/scan (mux)
     *   22:   i                base scan interval
     *   23:   p_sbx            polarity / scan blocks exponent
     *   24:   sb               scan/blocks
     *   25:   z_r1             hi=rec type, lo=rec len digit 1
     *   26:   r                rec len digits 2-3
     *   27:   str              scan types/record (2 BCD)
     *   28:   cs               channel sets/scan type (2 BCD)
     *   29:   sk               sample skew count (2 BCD)
     *   30:   ec               extended header count (2 BCD)
     *   31:   ex               external header count (2 BCD)
     * =================================================================== */
    if (read_block(fin, blk)) { fprintf(stderr,"Error: can't read GH1\n"); goto done; }

    /* Nibble indexing: byte[n] → nibbles 2n (high), 2n+1 (low) */
    int file_num  = bcd_nibbles(blk, 0, 4);   /* bytes 0-1 */
    int fmt_code  = (blk[2]<<8)|blk[3];        /* bytes 2-3 */
    int yr_bcd    = bcd_nibbles(blk, 20, 2);   /* byte 10 */
    int n_gh      = blk[11] >> 4;               /* byte 11 hi nibble */
    int day       = (blk[11] & 0x0F) * 100 +   /* byte 11 lo = day digit 1 */
                    (blk[12]>>4)*10             /* byte 12 hi = digit 2 */
                    + (blk[12]&0x0F);          /* byte 12 lo = digit 3 */
    int hour      = bcd_nibbles(blk, 26, 2);   /* byte 13 */
    int minute    = bcd_nibbles(blk, 28, 2);   /* byte 14 */
    int second    = bcd_nibbles(blk, 30, 2);   /* byte 15 */
    int mfg_code  = blk[16];                   /* byte 16 */
    int hdr1_i    = blk[22];                   /* byte 22 */
    int rec_len   = bcd_nibbles(blk, 51, 3);   /* byte 25 lo + byte 26 */
    int n_str     = bcd_nibbles(blk, 54, 2);   /* byte 27 */
    int n_cs      = bcd_nibbles(blk, 56, 2);   /* byte 28 */
    int n_sk      = bcd_nibbles(blk, 58, 2);   /* byte 29 */
    int n_ec      = bcd_nibbles(blk, 60, 2);   /* byte 30 */
    int n_ex      = bcd_nibbles(blk, 62, 2);   /* byte 31 */

    int year = yr_bcd;
    if (year < 30) year += 2000; else year += 1900;

    /* Sample count from GH1 */
    int ns = 0;
    if (rec_len != 999 && rec_len > 0 && hdr1_i > 0) {
        int r = rec_len * 2;
        ns = (r * 512 * 16) / (10 * hdr1_i) + 1;
    }

    /* Sample interval in μs */
    int dt_us = (hdr1_i * 1000) >> 4;
    if (dt_us < 100) dt_us = 2000;  /* sanity: 2ms default */

    if (verbose) {
        fprintf(stderr, "FFID=%d  Format=%04X  Mfg=%02X  Date=%04d-%03d %02d:%02d:%02d\n",
            file_num, fmt_code, mfg_code, year, day, hour, minute, second);
        fprintf(stderr, "n_gh=%d  rec_len=%d  i=%d  str=%d  cs=%d  sk=%d  ec=%d  ex=%d\n",
            n_gh, rec_len, hdr1_i, n_str, n_cs, n_sk, n_ec, n_ex);
        fprintf(stderr, "ns(GH1)=%d  dt=%dμs\n", ns, dt_us);
    }

    /* ===================================================================
     * GENERAL HEADERS #2..N
     * =================================================================== */
    int n_gt = 0, ep_val = 0;
    for (int i = 0; i < n_gh; i++) {
        if (read_block(fin, blk)) goto done;
        if (i == 0) {
            n_gt = (blk[14]<<8)|blk[15];   /* GH2 bytes 14-15 = trailer count */
            if (verbose) fprintf(stderr,"GH2: rev=%02x%02x  n_gt=%d\n", blk[10], blk[11], n_gt);
        } else if (i == 1) {
            /* GH3: source point number — 5 BCD digits at bytes 8-12 */
            ep_val = bcd_nibbles(blk, 16, 5);
            if (verbose) fprintf(stderr,"GH3: SP=%d\n", ep_val);
        }
    }

    /* ===================================================================
     * CHANNEL SET HEADERS + SAMPLE SKEW
     * =================================================================== */
    uint8_t *csh_data = NULL;
    int n_chan = 0;

    if (n_str > 0 && n_cs > 0) {
        csh_data = malloc(n_str * n_cs * SEGD_BLOCK);
        int idx = 0;
        for (int s = 0; s < n_str; s++) {
            for (int c = 0; c < n_cs; c++) {
                if (read_block(fin, csh_data + idx * SEGD_BLOCK)) goto done;
                uint8_t *cs = csh_data + idx * SEGD_BLOCK;
                n_chan += bcd_nibbles(cs, 0, 4);   /* cs_num: 4 BCD digits */
                idx++;
            }
            for (int k = 0; k < n_sk; k++) read_block(fin, blk);
        }
        if (verbose) {
            idx = 0;
            for (int s = 0; s < n_str; s++)
                for (int c = 0; c < n_cs; c++) {
                    uint8_t *cs = csh_data + idx * SEGD_BLOCK;
                    int chcnt = bcd_nibbles(cs, 0, 4);
                    fprintf(stderr, "  CS[%d][%d]: chans=%d type=%02x tf=%d te=%d mp=%02x%02x\n",
                        s, c, chcnt, cs[8], (cs[4]<<8)|cs[5], (cs[6]<<8)|cs[7], cs[10], cs[11]);
                    idx++;
                }
        }
    }
    if (verbose) fprintf(stderr, "Total channels: %d\n", n_chan);

    /* Fallback ns from channel set header */
    if ((ns == 0 || ns > 100000) && csh_data && hdr1_i > 0) {
        for (int s = 0; s < n_str && s < 1; s++)
            for (int c = 0; c < n_cs && c < 1; c++) {
                uint8_t *cs = csh_data + (s * n_cs + c) * SEGD_BLOCK;
                int te = (cs[6]<<8)|cs[7];
                int tf = (cs[4]<<8)|cs[5];
                if (te > tf) {
                    ns = 2 * (te - tf) * (16 << (cs[9]>>4)) / hdr1_i + 1;
                }
            }
    }

    if (ns_override > 0) ns = ns_override;
    if (ns <= 0 || ns > 100000) ns = 4000;  /* last resort */

    if (verbose) fprintf(stderr, "ns=%d  dt=%dμs  n_chan=%d  n_gt=%d  SP=%d\n",
        ns, dt_us, n_chan, n_gt, ep_val);

    /* ===================================================================
     * SKIP EXTENDED & EXTERNAL HEADERS
     * =================================================================== */
    for (int i = 0; i < n_ec; i++) read_block(fin, blk);
    for (int i = 0; i < n_ex; i++) read_block(fin, blk);

    /* ===================================================================
     * WRITE SEG-Y FILE HEADERS
     * =================================================================== */
    uint8_t hdr_buf[SEGY_TXT_SIZE > SEGY_BIN_SIZE ? SEGY_TXT_SIZE : SEGY_BIN_SIZE];
    segy_text_header(hdr_buf, inpath);
    if (fwrite(hdr_buf, 1, SEGY_TXT_SIZE, fout) != SEGY_TXT_SIZE) goto done;

    segy_bin_header(hdr_buf, ns, dt_us);
    if (fwrite(hdr_buf, 1, SEGY_BIN_SIZE, fout) != SEGY_BIN_SIZE) goto done;

    /* ===================================================================
     * TRACE LOOP
     * =================================================================== */
    int nbytes = ((ns + 3) / 4) * 10;
    float *samples = malloc(ns * sizeof(float));
    uint8_t *data_buf = malloc(nbytes);
    if (!samples || !data_buf) { fprintf(stderr, "malloc(%d) fail\n", ns); goto done; }

    int use_ffid = ffid_override ? ffid_override : file_num;
    int nwritten = 0, tif = 0;

    for (int itr = 0; itr < n_chan; itr++) {
        uint8_t dth[DEMUX_TRH_SIZE];
        if (fread(dth, 1, DEMUX_TRH_SIZE, fin) != DEMUX_TRH_SIZE) {
            if (verbose) fprintf(stderr, "  EOF at trace %d/%d\n", itr, n_chan);
            break;
        }

        int scan_raw = dth[2];       /* scan type — RAW on Fairfield */
        int chan_raw = dth[3];       /* chan set — RAW on Fairfield */
        int trace_nr = bcd_nibbles(dth, 8, 4);   /* tn: bytes 4-5 BCD */
        int the      = dth[9];                    /* trace header ext count */

        /* Skip trace header extensions */
        for (int e = 0; e < the; e++) read_block(fin, blk);

        /* Determine trace type */
        int trid = 1;  /* default seismic */
        int si = (scan_raw < n_str) ? scan_raw : 0;
        int ci = (chan_raw < n_cs)  ? chan_raw : 0;
        if (csh_data) {
            uint8_t *cs = csh_data + (si * n_cs + ci) * SEGD_BLOCK;
            switch (cs[8]) {
                case 0x10: trid = 1; break;
                case 0x20: trid = 3; break;   /* time break */
                case 0x30: trid = 4; break;   /* uphole */
                case 0x40: trid = 9; break;   /* water break */
                default:   trid = 2; break;   /* dead/aux */
            }
        }

        /* Read 8015 samples */
        int nrd = (int)fread(data_buf, 1, nbytes, fin);
        if (nrd < nbytes) memset(data_buf + nrd, 0, nbytes - nrd);
        decode_8015(data_buf, samples, ns);

        /* Apply gain */
        if (gain_flag && csh_data) {
            uint8_t *cs = csh_data + (si * n_cs + ci) * SEGD_BLOCK;
            float mp = (float)(((cs[11] & 0x7F) << 8) | cs[10]) / 1024.0f;
            if (cs[11] >> 7) mp = -mp;
            float gain = (float)pow(2.0, mp);
            if (gain != 1.0f)
                for (int j = 0; j < ns; j++) samples[j] *= gain;
        }

        tif++;
        if (trace_nr == 0) trace_nr = tif;

        /* Delay from channel set start time */
        int delrt = 0;
        if (csh_data) {
            uint8_t *cs = csh_data;
            delrt = ((cs[4]<<8)|cs[5]) * 2;
        }

        segy_trh(hdr_buf,          /* reuse buffer for trace header */
            nwritten + 1,          /* tracl */
            use_ffid,              /* fldr */
            trace_nr,              /* tracf */
            ep_val,                /* ep */
            trid,                  /* trid */
            ns, dt_us, delrt,
            year, day, hour, minute, second);

        if (fwrite(hdr_buf, 1, SEGY_TRH_SIZE, fout) != SEGY_TRH_SIZE) break;

        /* Write float data in big-endian */
        for (int j = 0; j < ns; j++) {
            w_fl32(data_buf, j*4, samples[j]);  /* pack into data_buf */
        }
        if (fwrite(data_buf, 4, ns, fout) != (size_t)ns) {
            fprintf(stderr,"Error writing trace data %d\n", nwritten);
            break;
        }

        nwritten++;
        if (verbose && nwritten % 100 == 0)
            fprintf(stderr, "  %d traces\n", nwritten);
    }

    /* Skip general trailer */
    for (int i = 0; i < n_gt; i++) read_block(fin, blk);

    if (verbose) fprintf(stderr, "Done: %d traces\n", nwritten);
    ret = 0;

done:
    if (fin) fclose(fin);
    if (fout && fout != stdout) fclose(fout);
    free(csh_data);
    free(samples);
    free(data_buf);
    return ret;
}
