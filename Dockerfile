# 1) ffmpeg 6.1이 포함된 베이스 이미지 (drawtext 지원)
FROM jrottenberg/ffmpeg:6.1-ubuntu2204 as ffmpeg

# 2) Python 3.10이 포함된 베이스 이미지
FROM python:3.10-slim-bullseye

# 작업 디렉토리
WORKDIR /app

# 3) ffmpeg 바이너리 복사
COPY --from=ffmpeg /usr/local /usr/local
COPY --from=ffmpeg /usr/lib /usr/lib
COPY --from=ffmpeg /lib /lib

# 4) ffmpeg 동작 확인용 패키지
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 5) Python 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6) 소스 복사
COPY . .
RUN mkdir -p /app/tmp
COPY tmp/ tmp/

# 7) 포트 노출 및 실행
EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "${PORT:-8080}", "--log-level", "debug"]
