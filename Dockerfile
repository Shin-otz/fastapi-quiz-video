FROM python:3.12-bullseye as python
FROM jrottenberg/ffmpeg:7.0-ubuntu2204 as ffmpeg

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
