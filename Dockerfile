FROM python:3.10-slim-bullseye AS builder

WORKDIR /tmp

# ffmpeg 빌드에 필요한 패키지
RUN apt-get update && apt-get install -y \
    autoconf automake build-essential cmake git-core pkg-config \
    libass-dev libfreetype6-dev libfontconfig1-dev \
    libvorbis-dev libx264-dev libx265-dev \
    libopus-dev libvpx-dev yasm nasm wget curl \
    && rm -rf /var/lib/apt/lists/*

# ffmpeg 빌드
RUN git clone --depth 1 --branch n6.1 https://git.ffmpeg.org/ffmpeg.git ffmpeg && \
    cd ffmpeg && \
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

# 폰트 설치 (drawtext에서 한글 필요시)
RUN apt-get update && apt-get install -y \
    libfreetype6 libfontconfig1 fonts-nanum fonts-noto-cjk && \
    rm -rf /var/lib/apt/lists/*

# 빌드한 ffmpeg 복사
COPY --from=builder /ffmpeg-build/ /usr/local/

# ffmpeg drawtext 필터 확인
RUN ffmpeg -version && ffmpeg -filters | grep drawtext || (echo "❌ drawtext 없음!" && exit 1)

# 파이썬 라이브러리
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 복사
COPY . .
RUN mkdir -p /app/tmp

EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--log-level", "debug"]
