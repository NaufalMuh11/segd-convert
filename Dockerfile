# ============================================================
# SeisUnix Docker Image — segdread manual compile
# Strategy: bypass Stdio_s yang bermasalah, compile segdread
# langsung dengan libsfio.a yang berhasil dibuild
# Base: Ubuntu 16.04
# ============================================================

FROM ubuntu:16.04

ENV DEBIAN_FRONTEND=noninteractive
ENV CWPROOT=/opt/cwp/SeisUnix
ENV PATH=$PATH:/opt/cwp/SeisUnix/bin

# ------------------------------------------------------------
# 1. Install dependencies
# ------------------------------------------------------------
RUN apt-get update && apt-get install -y \
    git make gcc g++ gfortran \
    libx11-dev libxt-dev libxmu-dev libxi-dev \
    freeglut3-dev libmotif-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# ------------------------------------------------------------
# 2. Clone SeisUnix
# ------------------------------------------------------------
RUN mkdir -p /opt/cwp && \
    git clone --depth=1 https://github.com/JohnWStockwellJr/SeisUnix.git $CWPROOT

# ------------------------------------------------------------
# 3. Bypass license
# ------------------------------------------------------------
RUN touch $CWPROOT/src/LICENSE_45R00_ACCEPTED
RUN mkdir -p $CWPROOT/bin $CWPROOT/lib $CWPROOT/include

# ------------------------------------------------------------
# 4. Compile core SU (segyread, sufilter, dll)
# ------------------------------------------------------------
WORKDIR $CWPROOT/src
RUN yes | make install || true

# ------------------------------------------------------------
# 5. Compile Sfio — HANYA vthread + libsfio.a (skip Stdio_s)
# ------------------------------------------------------------
WORKDIR $CWPROOT/src/Sfio/src/lib/vthread
RUN make install CWPROOT=$CWPROOT || true

WORKDIR $CWPROOT/src/Sfio/src/lib/sfio
# Compile semua .o kecuali Stdio_s dan Stdio_b
RUN make LIBTYPE="-Dvt_threaded=0" CC=cc CCMODE="-O" \
    sfclose.o sfclrlock.o sfcvt.o sfdisc.o sfdlen.o sfexcept.o \
    sfextern.o sffilbuf.o sfflsbuf.o sfprints.o sfgetd.o sfgetl.o \
    sfgetr.o sfgetu.o sfllen.o sfmode.o sfmove.o sfnew.o sfnotify.o \
    sfnputc.o sfopen.o sfpkrd.o sfpool.o sfpopen.o sfprintf.o \
    sfputd.o sfputl.o sfputr.o sfputu.o sfrd.o sfread.o sfscanf.o \
    sfseek.o sfset.o sfsetbuf.o sfsetfd.o sfsize.o sfsk.o sfstack.o \
    sfsync.o sftable.o sftell.o sftmp.o sfungetc.o sfvprintf.o \
    sfvscanf.o sfwr.o sfwrite.o sfexit.o sfpurge.o sfpoll.o \
    sfreserve.o sfswap.o sfraise.o sfmutex.o sfgetm.o sfputm.o \
    sfresize.o sffrexp.o \
    _sfclrerr.o _sfdlen.o _sfeof.o _sferror.o _sffileno.o \
    _sfgetc.o _sfgetl.o _sfgetl2.o _sfgetu.o _sfgetu2.o _sfllen.o \
    _sfopen.o _sfputc.o _sfputd.o _sfputl.o _sfputm.o _sfputu.o \
    _sfslen.o _sfstacked.o _sfulen.o _sfvalue.o || true

# Buat libsfio.a dari .o yang berhasil dikompile
RUN ar cr $CWPROOT/lib/libsfio.a *.o 2>/dev/null || true && \
    ranlib $CWPROOT/lib/libsfio.a 2>/dev/null || true

# Copy header Sfio ke include
RUN cp $CWPROOT/src/Sfio/src/lib/sfio/sfio.h $CWPROOT/include/ 2>/dev/null || true && \
    cp $CWPROOT/src/Sfio/include/*.h $CWPROOT/include/ 2>/dev/null || true

# ------------------------------------------------------------
# 6. Compile segdread secara manual
# ------------------------------------------------------------
WORKDIR $CWPROOT/src/Sfio/main

RUN gcc -I$CWPROOT/include \
    -I$CWPROOT/src/Sfio/src/lib/sfio \
    -I$CWPROOT/src/Sfio/include \
    -O segdread.c \
    -L$CWPROOT/lib \
    -lsfio -lsu -lpar -lcwp -lm \
    -o $CWPROOT/bin/segdread 2>&1 || \
    echo "==> segdread compile attempt done, check errors above"

RUN ls -la $CWPROOT/bin/segdread 2>/dev/null && \
    echo "SUCCESS: segdread compiled!" || \
    echo "FAILED: segdread not found"

# ------------------------------------------------------------
# 7. Direktori kerja
# ------------------------------------------------------------
RUN mkdir -p /data /output
WORKDIR /data
CMD ["/bin/bash"]
