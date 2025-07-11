# Python 3.12 기반 경량 이미지
FROM python:3.12-slim

# 필수 패키지 설치: ffmpeg 포함
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    which ffmpeg && \
    ffmpeg -version && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# 앱 폴더 설정
WORKDIR /app
COPY . .

# Python 의존성 설치
RUN pip install --no-cache-dir -r requirements.txt

# FastAPI 서버 실행
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--log-level", "debug"]
