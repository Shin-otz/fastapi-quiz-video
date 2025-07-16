# Python 3.12 기반 경량 이미지
FROM python:3.12-slim

# 필수 패키지
RUN apt-get update && apt-get install -y wget xz-utils && rm -rf /var/lib/apt/lists/*

# 최신 ffmpeg 7.0 static binary 다운로드
RUN wget https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz \
    && tar -xf ffmpeg-release-amd64-static.tar.xz \
    && mv ffmpeg-*-amd64-static/ffmpeg /usr/local/bin/ffmpeg \
    && mv ffmpeg-*-amd64-static/ffprobe /usr/local/bin/ffprobe \
    && chmod +x /usr/local/bin/ffmpeg /usr/local/bin/ffprobe \
    && rm -rf ffmpeg-release-amd64-static*

# ffmpeg 버전 출력 확인
RUN ffmpeg -version

# 앱 폴더 설정
WORKDIR /app
COPY . .
COPY tmp/ tmp/

# Python 의존성 설치
RUN pip install --no-cache-dir -r requirements.txt


# FastAPI 서버 실행
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--log-level", "debug"]
