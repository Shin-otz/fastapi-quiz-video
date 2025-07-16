FROM python:3.10-slim-bullseye

WORKDIR /app

# 필요한 패키지 설치
RUN apt-get update && apt-get install -y \
    autoconf automake build-essential cmake git-core pkg-config \
    libass-dev libfreetype6-dev libfontconfig1-dev \
    libvorbis-dev libx264-dev libx265-dev \
    libopus-dev libvpx-dev yasm nasm wget curl \
    libfreetype6 libfontconfig1 \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# ffmpeg 6.1 소스 빌드
RUN git clone --depth 1 --branch n6.1 https://git.ffmpeg.org/ffmpeg.git ffmpeg && \
    cd ffmpeg && \
    ./configure \
        --prefix=/usr/local \
        --enable-gpl \
        --enable-libfreetype \
        --enable-libfontconfig \
        --enable-libx264 \
        --enable-libx265 \
        --enable-libvorbis \
        --enable-libopus \
        --enable-libvpx \
        --enable-nonfree && \
    make -j$(nproc) && make install && \
    cd .. && rm -rf ffmpeg

# ffmpeg 설치 및 drawtext 필터 확인
RUN ffmpeg -version && ffmpeg -filters | grep drawtext || (echo "❌ drawtext 필터 없음!" && exit 1)

# Python 패키지 설치
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 소스 복사
COPY . ./
RUN mkdir -p /app/tmp
COPY tmp/ tmp/

EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--log-level", "debug"]
