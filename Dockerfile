# Python 3.12 기반 경량 이미지
FROM python:3.12-slim

# 작업 디렉토리
WORKDIR /app

# 필수 패키지 설치 및 ffmpeg 7.1.1 설치

# 1️⃣ 빌드에 필요한 패키지 설치
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    yasm \
    nasm \
    pkg-config \
    libx264-dev \
    libx265-dev \
    libvpx-dev \
    libfdk-aac-dev \
    libopus-dev \
    libass-dev \
    libfreetype6-dev \
    wget \
    xz-utils \
    && rm -rf /var/lib/apt/lists/*

# 2️⃣ ffmpeg 소스 다운로드 & 7.1.1 체크아웃 & 빌드
RUN git clone https://git.ffmpeg.org/ffmpeg.git ffmpeg && \
    cd ffmpeg && \
    git checkout n7.1.1 && \
    ./configure \
      --prefix=/usr/local \
      --pkg-config-flags="--static" \
      --extra-cflags="-I/usr/local/include" \
      --extra-ldflags="-L/usr/local/lib" \
      --extra-libs="-lpthread -lm" \
      --bindir=/usr/local/bin \
      --enable-gpl \
      --enable-nonfree \
      --enable-libx264 \
      --enable-libx265 \
      --enable-libvpx \
      --enable-libfdk-aac \
      --enable-libopus \
      --enable-libass \
      --enable-libfreetype \
    && make -j$(nproc) && make install && \
    strip /usr/local/bin/ffmpeg && strip /usr/local/bin/ffprobe && \
    cd .. && rm -rf ffmpeg

# Python 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 소스 복사
COPY . .
COPY tmp/ tmp/

# tmp 폴더가 필요하면 아래 주석 해제
# RUN mkdir -p /app/tmp

# FastAPI 서버 실행
EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--log-level", "debug"]
