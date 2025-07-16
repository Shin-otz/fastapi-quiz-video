# ========== [ 1단계: ffmpeg 빌드 ] ==========
FROM python:3.10-slim-bullseye AS builder

# 빌드 작업 디렉토리
WORKDIR /usr/local/src

# ffmpeg 빌드에 필요한 패키지 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    autoconf \
    automake \
    build-essential \
    pkg-config \
    yasm \
    nasm \
    wget \
    ca-certificates \
    libx264-dev \
    libx265-dev \
    libvpx-dev \
    libopus-dev \
    libvorbis-dev \
    && rm -rf /var/lib/apt/lists/*

# ffmpeg 7.0.2 다운로드 및 빌드
RUN wget https://ffmpeg.org/releases/ffmpeg-7.0.2.tar.gz && \
    tar xzf ffmpeg-7.0.2.tar.gz && \
    cd ffmpeg-7.0.2 && \
    ./configure \
        --prefix=/usr/local \
        --enable-gpl \
        --enable-libx264 \
        --enable-libx265 \
        --enable-libvorbis \
        --enable-libopus \
        --enable-libvpx \
        --enable-nonfree && \
    make -j"$(nproc)" && make install


# ========== [ 2단계: 런타임 실행 환경 ] ==========
FROM python:3.10-slim-bullseye AS runtime

# 앱 실행 경로
WORKDIR /app

# ffmpeg 실행에 필요한 런타임 라이브러리만 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    libx264-163 \
    libx265-199 \
    libvpx7 \
    libopus0 \
    libvorbis0a \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 빌드된 ffmpeg 복사
COPY --from=builder /usr/local/ /usr/local/

# 파이썬 패키지 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 소스 복사
COPY . .
COPY tmp/ tmp/
# 포트 노출
EXPOSE 8080

# Railway의 PORT 환경변수에 맞춰 실행
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080} --log-level debug"]
