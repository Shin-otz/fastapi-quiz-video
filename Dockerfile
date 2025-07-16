FROM python:3.10-slim

# ffmpeg 스태틱 바이너리 다운로드 준비
RUN apt-get update && apt-get install -y wget xz-utils && rm -rf /var/lib/apt/lists/*

# ffmpeg 최신 7.0 스태틱 다운로드
RUN wget https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz \
    && tar -xf ffmpeg-release-amd64-static.tar.xz \
    && mv ffmpeg-*-amd64-static/ffmpeg /usr/local/bin/ffmpeg \
    && mv ffmpeg-*-amd64-static/ffprobe /usr/local/bin/ffprobe \
    && chmod +x /usr/local/bin/ffmpeg /usr/local/bin/ffprobe \
    && rm -rf ffmpeg-release-amd64-static*

# ffmpeg 설치 확인
RUN ffmpeg -version

WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 소스 복사
COPY . .
COPY tmp/ tmp/
# 포트 노출
EXPOSE 8080

# Railway의 PORT 환경변수에 맞춰 실행
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080} --log-level debug"]
