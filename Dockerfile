FROM jrottenberg/ffmpeg:7.0-ubuntu2204

WORKDIR /app

# python3 설치
RUN apt-get update && apt-get install -y \
    python3 python3-pip python3-dev python3-distutils build-essential \
    libgl1-mesa-glx libglib2.0-0 \
    && ln -s /usr/bin/python3 /usr/local/bin/python \
    && ln -s /usr/bin/pip3 /usr/local/bin/pip \
    && python --version && pip --version

# 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 복사
COPY . .

# tmp 폴더
RUN mkdir -p /app/tmp
COPY tmp/ tmp/

EXPOSE 8080
# Railway가 PORT를 전달하므로 ${PORT} 사용
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080} --log-level debug
