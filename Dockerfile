FROM jrottenberg/ffmpeg:7.0-ubuntu2204

# Python 3.12 설치
RUN apt-get update && apt-get install -y python3.12 python3.12-distutils python3-pip \
    && ln -s /usr/bin/python3.12 /usr/local/bin/python3 \
    && ln -s /usr/bin/pip3 /usr/local/bin/pip

WORKDIR /app

# 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /app/tmp
COPY tmp/ tmp/

EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--log-level", "debug"]
