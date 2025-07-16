# 1️⃣ Python 3.12가 포함된 베이스
FROM python:3.12-bullseye

# 2️⃣ 작업 디렉토리
WORKDIR /app

# 3️⃣ ffmpeg 7.0.2 (drawtext 포함) 이미지에서 필요한 바이너리만 복사
COPY --from=jrottenberg/ffmpeg:7.0-ubuntu2204 /usr/local /usr/local
COPY --from=jrottenberg/ffmpeg:7.0-ubuntu2204 /usr/lib /usr/lib
COPY --from=jrottenberg/ffmpeg:7.0-ubuntu2204 /lib /lib

# 4️⃣ ffmpeg drawtext 필터가 있는지 확인 (빌드 시점 테스트)
RUN ffmpeg -filters | grep drawtext || (echo "❌ drawtext 필터 없음!" && exit 1)

# 5️⃣ Python 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6️⃣ 소스 코드 복사
COPY . .
RUN mkdir -p /app/tmp
COPY tmp/ tmp/

# 7️⃣ 포트 개방 및 실행 명령
EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--log-level", "debug"]
