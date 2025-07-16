# ffmpeg 7.0.2 + drawtext 지원되는 jrottenberg 이미지 사용
FROM jrottenberg/ffmpeg:7.0-ubuntu2204

# 작업 디렉토리
WORKDIR /app

# python3, pip 설치 (ubuntu 22.04 기본)
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-distutils \
    && ln -s /usr/bin/python3 /usr/local/bin/python \
    && ln -s /usr/bin/pip3 /usr/local/bin/pip \
    && python --version \
    && pip --version

# Python requirements 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 앱 소스 복사
COPY . .
RUN mkdir -p /app/tmp
COPY tmp/ tmp/

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--log-level", "debug"]
