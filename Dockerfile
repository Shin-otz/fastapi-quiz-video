FROM python:3.12-slim

WORKDIR /app

# ffmpeg 7.0.2 고정 설치
RUN apt-get update && apt-get install -y wget xz-utils && \
    wget https://johnvansickle.com/ffmpeg/releases/ffmpeg-7.0.2-amd64-static.tar.xz && \
    tar -xf ffmpeg-7.0.2-amd64-static.tar.xz && \
    mv ffmpeg-7.0.2-amd64-static/ffmpeg /usr/local/bin/ffmpeg && \
    mv ffmpeg-7.0.2-amd64-static/ffprobe /usr/local/bin/ffprobe && \
    chmod +x /usr/local/bin/ffmpeg /usr/local/bin/ffprobe && \
    ffmpeg -version && \
    rm -rf ffmpeg-7.0.2-amd64-static* && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Python 의존성
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 복사
COPY . .
COPY tmp/ tmp/

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--log-level", "debug"]
