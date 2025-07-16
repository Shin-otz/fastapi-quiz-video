FROM python:3.12-slim

WORKDIR /app

# ffmpeg 빌드에 필요한 패키지 (폰트, freetype, fontconfig 포함)
RUN apt-get update && apt-get install -y \
    wget \
    xz-utils \
    libfreetype6 libfreetype6-dev \
    libfontconfig1 libfontconfig1-dev \
    && rm -rf /var/lib/apt/lists/*

# ffmpeg 7.0.2 static 빌드 다운로드 및 설치
RUN wget https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz && \
    tar -xf ffmpeg-release-amd64-static.tar.xz && \
    mv ffmpeg-*-amd64-static/ffmpeg /usr/local/bin/ffmpeg && \
    mv ffmpeg-*-amd64-static/ffprobe /usr/local/bin/ffprobe && \
    chmod +x /usr/local/bin/ffmpeg /usr/local/bin/ffprobe && \
    ffmpeg -version && \
    rm -rf ffmpeg-*-amd64-static* && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Python 의존성
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 복사
COPY . .
COPY tmp/ tmp/

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--log-level", "debug"]
