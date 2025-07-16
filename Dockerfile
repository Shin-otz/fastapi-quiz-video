FROM jrottenberg/ffmpeg:7.0-ubuntu2204

# ✅ Python 3.10 (기본 Ubuntu 22.04 제공) 설치
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-distutils \
    && ln -s /usr/bin/python3 /usr/local/bin/python \
    && ln -s /usr/bin/pip3 /usr/local/bin/pip \
    && python --version \
    && pip --version

WORKDIR /app

# ✅ 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ✅ 앱 복사
COPY . .
RUN mkdir -p /app/tmp
COPY tmp/ tmp/

EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--log-level", "debug"]
