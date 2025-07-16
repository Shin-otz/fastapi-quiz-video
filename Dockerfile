FROM python:3.12-bullseye

WORKDIR /app

# 필수 빌드 도구 및 라이브러리 설치
RUN apt-get update && apt-get install -y \
    autoconf automake build-essential cmake git-core pkg-config \
    libass-dev libfreetype6-dev libfontconfig1-dev \
    libtool libvorbis-dev libopus-dev libvpx-dev \
    yasm nasm wget curl \
    && rm -rf /var/lib/apt/lists/*

# ffmpeg 소스 클론 (7.0.2)
RUN git clone --depth 1 --branch n7.0.2 https://git.ffmpeg.org/ffmpeg.git ffmpeg

WORKDIR /app/ffmpeg

# ffmpeg 빌드
RUN ./configure \
    --prefix=/usr/local \
    --enable-gpl \
    --enable-libfreetype \
    --enable-libfontconfig \
    --enable-libass \
    --enable-libvorbis \
    --enable-libopus \
    --enable-libvpx \
    --enable-nonfree \
    --disable-debug \
    --disable-doc \
    --disable-ffplay \
    && make -j$(nproc) \
    && make install


WORKDIR /app

# Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 복사 (tmp 폴더가 실제로 있어야 함)
COPY . .
RUN mkdir -p /app/tmp
COPY tmp/ tmp/

EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--log-level", "debug"]
