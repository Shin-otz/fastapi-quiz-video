# drawtext 포함된 ffmpeg 베이스 이미지
FROM jrottenberg/ffmpeg:7.0-ubuntu2204 as ffmpeg

# Python 환경을 추가하기 위해 python base에서 시작
FROM python:3.12-slim

WORKDIR /app

# ffmpeg 복사 (멀티 스테이지)
COPY --from=ffmpeg / /

# Python requirements 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 복사
COPY . .
RUN mkdir -p /app/tmp
COPY tmp/ tmp/

EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--log-level", "debug"]
