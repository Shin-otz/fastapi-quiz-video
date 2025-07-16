FROM python:3.12-slim

WORKDIR /app

# ffmpeg (Debian 패키지) 설치
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && \
    ffmpeg -version && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Python 의존성
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 복사
COPY . .
COPY tmp/ tmp/

EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--log-level", "debug"]
