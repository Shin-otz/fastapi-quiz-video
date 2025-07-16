FROM python:3.12-bullseye

WORKDIR /app

# ffmpeg 빌드에 필요한 종속성 설치
RUN apt-get update && apt-get install -y \
    autoconf automake build-essential cmake git-core pkg-config \
    libass-dev libfreetype6-dev libfontconfig1-dev \
    libvorbis-dev libx264-dev libx265-dev \
    libopus-dev libvpx-dev yasm nasm \
    wget && rm -rf /var/lib/apt/lists/*

# ffmpeg 소스 클론 (7.0.2 태그 사용)
RUN git clone --depth 1 --branch n7.0.2 https://git.ffmpeg.org/ffmpeg.git ffmpeg

WORKDIR /app/ffmpeg

# ffmpeg 빌드
RUN ./configure \
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
    make -j$(nproc) && \
    make install

# ffmpeg 설치 확인
RUN ffmpeg -version && ffmpeg -filters | grep drawtext

WORKDIR /app

# Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 복사
COPY . .
COPY tmp/ tmp/

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--log-level", "debug"]
