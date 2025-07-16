FROM python:3.10-slim-bullseye AS builder

WORKDIR /tmp

# 빌드 종속성 설치
RUN apt-get update && apt-get install -y \
    autoconf automake build-essential cmake git-core pkg-config \
    libass-dev libfreetype6-dev libfontconfig1-dev \
    libvorbis-dev libx264-dev libx265-dev \
    libopus-dev libvpx-dev yasm nasm wget curl \
    && rm -rf /var/lib/apt/lists/*

# ffmpeg 최신 버전 다운로드 (7.1)
RUN wget https://ffmpeg.org/releases/ffmpeg-7.1.tar.gz && \
    tar xzf ffmpeg-7.1.tar.gz && \
    cd ffmpeg-7.1 && \
    ./configure \
        --prefix=/ffmpeg-build \
        --enable-gpl \
        --enable-libfreetype \
        --enable-libfontconfig \
        --enable-libx264 \
        --enable-libx265 \
        --enable-libvorbis \
        --enable-libopus \
        --enable-libvpx \
        --enable-nonfree && \
    make -j$(nproc) && make install

# -------------------------------------------------
FROM python:3.10-slim-bullseye AS runtime

WORKDIR /app

# drawtext용 폰트 설치 (한글 포함)
RUN apt-get update && apt-get install -y \
    libfreetype6 libfontconfig1 fonts-nanum fonts-noto-cjk && \
    rm -rf /var/lib/apt/lists/*

# 빌드된 ffmpeg 복사
COPY --from=builder /ffmpeg-build/ /usr/local/

# ffmpeg 확인
RUN ffmpeg -version && ffmpeg -filters | grep drawtext || (echo "❌ drawtext 없음!" && exit 1)

# Python 패키지 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
