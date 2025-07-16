FROM python:3.12-slim

WORKDIR /app

# 빌드에 필요한 도구 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    autoconf automake build-essential cmake git pkg-config yasm nasm \
    libx264-dev libx265-dev libvpx-dev libopus-dev libfdk-aac-dev libass-dev \
    && rm -rf /var/lib/apt/lists/*

# ffmpeg 최신 소스 빌드 (2025-07-12 기준 최신 master)
RUN git clone https://git.ffmpeg.org/ffmpeg.git ffmpeg-src && \
    cd ffmpeg-src && \
    git checkout master && \
    ./configure \
        --enable-gpl \
        --enable-libx264 \
        --enable-libx265 \
        --enable-libvpx \
        --enable-libfdk-aac \
        --enable-libopus \
        --enable-libass \
        --enable-nonfree && \
    make -j$(nproc) && make install && \
    cd .. && rm -rf ffmpeg-src

# ffmpeg 설치 확인
RUN ffmpeg -version

# Python 의존성
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 복사
COPY . .
COPY tmp/ tmp/

EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--log-level", "debug"]
