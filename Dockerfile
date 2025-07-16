# ✅ 1단계: ffmpeg가 이미 설치된 ubuntu2204 베이스
FROM jrottenberg/ffmpeg:7.0-ubuntu2204 as ffmpeg

# ✅ 2단계: python 3.12 + ffmpeg 바이너리 복사
FROM python:3.12-slim-bullseye

# 작업 디렉토리
WORKDIR /app

# ffmpeg 복사 (glibc 호환)
COPY --from=ffmpeg /usr/local /usr/local
COPY --from=ffmpeg /usr/lib /usr/lib
COPY --from=ffmpeg /lib /lib

# Python 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 앱 소스 복사
COPY . .
RUN mkdir -p /app/tmp
COPY tmp/ tmp/

# 포트와 실행
EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--log-level", "debug"]
