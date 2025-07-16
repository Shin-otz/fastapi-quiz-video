FROM jrottenberg/ffmpeg:7.0-ubuntu2204

WORKDIR /app


# python3, pip 설치
RUN apt-get update && apt-get install -y \
    python3 python3-pip python3-dev python3-distutils build-essential \
    libgl1-mesa-glx libglib2.0-0 \
    && ln -s /usr/bin/python3 /usr/local/bin/python \
    && ln -s /usr/bin/pip3 /usr/local/bin/pip

# requirements.txt 복사 후 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 복사
COPY . .
RUN mkdir -p /app/tmp
COPY tmp/ tmp/
EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--log-level", "debug"]
