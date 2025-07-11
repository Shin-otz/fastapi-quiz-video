import subprocess
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import logging
import uvicorn
import ffmpeg
import requests
from pathlib import Path
import sys
import re
import uuid
import traceback
import mimetypes
import os
import logging
import json
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow


def get_drive_service():
    """
    인증된 토큰(JSON)을 바탕으로 Google Drive API 클라이언트를 생성
    """
    if "GOOGLE_TOKENS_JSON" not in os.environ:
        print("⚠️ GOOGLE_TOKENS_JSON이 없습니다. Drive API 클라이언트 생성을 건너뜁니다.")
        return None

    tokens = json.loads(os.environ["GOOGLE_TOKENS_JSON"])
    creds = Credentials.from_authorized_user_info(tokens)
    return build("drive", "v3", credentials=creds)

# 환경 변수에 OAuth 클라이언트 정보가 있는 경우만 동작
credentials_data = None
drive_service = None

if "GOOGLE_CREDENTIALS_JSON" in os.environ:
    credentials_data = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])
    drive_service = get_drive_service()
else:
    print("🔕 로컬 환경이거나 GOOGLE_CREDENTIALS_JSON이 없습니다. 인증 흐름은 비활성화됩니다.")

if drive_service:
    file = drive_service.files().get(fileId="...").execute()
else:
    print("⚠️ drive_service가 활성화되지 않았습니다.")

# uvicorn 로거 설정
logger = logging.getLogger("uvicorn")
logger.setLevel(logging.DEBUG)

app = FastAPI()

logger.debug("HAHa ...")

# tmp 폴더 생성
Path("tmp").mkdir(parents=True, exist_ok=True)

app = FastAPI()
app.mount("/static", StaticFiles(directory="tmp"), name="static")

class QuestionItem(BaseModel):
    question_type: str
    topic: str
    key_term: str
    question: str
    hint: str
    answer: str
    background_url: str
    image_url: str
    question_url: str
    answer_url: str
    explanation_url: str

class FileRequest(BaseModel):
    filename: str


def check_ffmpeg_installed():
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True
        )
        logger.info("✅ FFmpeg 설치  확인됨.")
    except FileNotFoundError:
        logger.error("❌ FFmpeg가 설치되어 있지 않습니다.")
        raise RuntimeError("FFmpeg가 시스템에 설치되어 있지 않습니다. apt 또는 brew로 설치하세요.")
    except subprocess.CalledProcessError as e:
        logger.error("❌ FFmpeg 실행 실패:")
        logger.error(e.stderr.decode())
        raise RuntimeError("FFmpeg가 실행 중 오류가 발생했습니다.")

def extract_drive_id(url: str) -> str:
    match = re.search(r"/d/([a-zA-Z0-9_-]+)", url)
    if match:
        return match.group(1)
    return str(uuid.uuid4())[:8]

def convert_drive_url(url: str) -> str:
    match = re.search(r"/d/([a-zA-Z0-9_-]+)", url)
    if not match:
        raise ValueError("올바른 Google Drive 링크가 아닙니다.")
    file_id = match.group(1)
    return f"https://drive.google.com/uc?export=download&id={file_id}"

"""
def download_file(url: str, filename: str) -> str:
    if "drive.google.com" in url:
        url = convert_drive_url(url)

    r = requests.get(url)
    r.raise_for_status()

    path = Path(f"tmp/{filename}")
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with open(path, "wb") as f:
            f.write(r.content)
    return str(path)
"""

def download_drive_file(file_id: str, filename: str) -> str:
    path = Path(f"tmp/{filename}")
    path.parent.mkdir(parents=True, exist_ok=True)

    drive_service = get_drive_service()
    request = drive_service.files().get_media(fileId=file_id)

    with open(path, "wb") as f:
        downloader = MediaIoBaseDownload(f, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()

    print(f"✅ 다운로드 완료: {path}")
    return str(path)

def create_video(image_path: str, audio_path: str, output_path: str):
    image_input = ffmpeg.input(image_path, loop=1, framerate=2)
    audio_input = ffmpeg.input(audio_path)
    # 2. 출력 설정 및 실행
    (
        ffmpeg
        .output(
            image_input,
            audio_input,
            output_path,
            vcodec='libx264',
            acodec='aac',
            audio_bitrate='192k',
            pix_fmt='yuv420p',
            shortest=None,  # shortest=True도 가능
            movflags='+faststart'
        )
        .run(overwrite_output=True)
    )

def create_video2(image_path: str, audio_path: str, output_path: str):
    try:
        logger.info(f"🎧 오디오 경로: {audio_path}")
        logger.info(f"🖼️ 이미지 경로: {image_path}")

        # 오디오 길이 확인
        probe = ffmpeg.probe(audio_path)
        logger.info(f"ffprobe 결과: {probe}")
        duration = float(probe["format"]["duration"])

        (
            ffmpeg
            .input(image_path, loop=1, t=duration)
            .input(audio_path)
            .output(output_path, vcodec='libx264', acodec='aac', pix_fmt='yuv420p', shortest=None)
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )

        logger.info(f"✅ 비디오 생성 완료: {output_path}")

    except ffmpeg.Error as e:
        logger.error("❌ FFmpeg 처리 오류 발생:")
        logger.error(e.stderr.decode())
        raise HTTPException(status_code=500, detail="FFmpeg 실행 오류")

    except Exception as ex:
        logger.error("❌ 일반 예외 발생:")
        logger.error(str(ex))
        raise HTTPException(status_code=500, detail=f"비디오 생성 중 알 수 없는 오류 발생{image_path} ::{audio_path} :: {output_path}")

@app.get("/")
def hello():
    logger.info("👋 INFO 로그 작동!")
    logger.debug("🐛 DEBUG 로그 작동!")
    file = Path(audio_file).exists()
    return {"message": "hello"}

#@app.exception_handler(Exception)
#async def general_exception_handler(request, exc):
#    logger.error(f"예외 발생: {traceback.format_exc()}")
#    return JSONResponse(status_code=500, content={"message": "Internal server error."})

def generate_unique_filename(prefix: str, ext: str, file_id: str) -> str:
    return f"{prefix}_{file_id}.{ext}"
@app.post("/generate-video")
async def generate_one(item: QuestionItem):
    logger.debug(f"질문: {item.question}")
    logger.debug(f"정답: {item.answer}")

    # 🔽 각 URL에서 Google Drive file_id 추출
    image_id = extract_drive_id(item.image_url)
    question_audio_id = extract_drive_id(item.question_url)
    answer_audio_id = extract_drive_id(item.answer_url)
    explanation_audio_id = extract_drive_id(item.explanation_url)
    background_id = extract_drive_id(item.background_url)

    # 🔽 Google Drive API로 파일 다운로드
    image_file = download_drive_file(image_id, generate_unique_filename("image", "png", image_id))
    audio_file = download_drive_file(question_audio_id, generate_unique_filename("question", "mp3", question_audio_id))
    answer_file = download_drive_file(answer_audio_id, generate_unique_filename("answer", "mp3", answer_audio_id))
    explanation_file = download_drive_file(explanation_audio_id, generate_unique_filename("explanation", "mp3", explanation_audio_id))
    background_image_file = download_drive_file(background_id, generate_unique_filename("background", "png", background_id))

    # 🔽 출력 파일명
    output_filename = f"video_{question_audio_id}.mp4"
    output_file = f"tmp/{output_filename}"

    create_video(image_file, audio_file, output_file)

    BASE_URL = "https://primary-production-8af2.up.railway.app"
    public_video_url = f"{BASE_URL}/static/{output_filename}"

    return {
        "status": "ok",
        "video_file": public_video_url,
        "video_file_exists": Path(output_file).exists(),
        "question": item.question,
        "answer": item.answer,
        "hint": item.hint,
        "key_term": item.key_term,
        "background_fn": Path(background_image_file).name,
        "image_fn": Path(image_file).name,
        "question_fn": Path(audio_file).name,
        "answer_fn": Path(answer_file).name,
        "explanation_fn": Path(explanation_file).name,
        "video_output_fn": output_filename,
        "Image": Path(background_image_file).exists(),
        "MP3": Path(audio_file).exists()
    }

@app.get("/get-media")
def get_media(filename: str):
    file_path = f"tmp/{filename}"

    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="파일이 존재하지 않습니다.")

    # 파일 MIME 타입 자동 추론 (jpg, png, mp4 등 지원)
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type is None:
        mime_type = "application/octet-stream"  # fallback

    return FileResponse(path=file_path, media_type=mime_type, filename=filename)

@app.post("/check-audio")
def check_audio_post(data: FileRequest):
    filename = data.filename
    file_path = Path(f"tmp/{filename}")
    if file_path.exists():
        return FileResponse(
            path=str(file_path),
            media_type="audio/mpeg",
            filename=filename
        )
    else:
        return {"error": f"{filename} not found"}


@app.get("/check-file")
def check_file(filename: str = Query(..., description="파일 이름")):
    file_path = Path(f"tmp/{filename}")

    if file_path.exists():
        # 확장자 기반 MIME 타입 추정
        media_type, _ = mimetypes.guess_type(str(file_path))
        if media_type is None:
            media_type = 'application/octet-stream'  # 기본값

        return FileResponse(
            path=str(file_path),
            media_type=media_type,
            filename=filename
        )
    else:
        return {"error": f"{filename} not found"}

@app.post("/check-video")
def check_video(filename: str):
    video_path = Path(f"tmp/{filename}")
    if video_path.exists():
        return FileResponse(
            path=str(video_path),
            media_type="video/mp4",
            filename=filename
        )
    else:
        return {"error": f"{filename} not found"}

@app.on_event("startup")
async def on_startup():
    check_ffmpeg_installed()
    logger.info("✅ FFmpeg 설치 확인됨, 서버 시작!")

if __name__ == "__main__":
    logger.info("Starting ...")
    uvicorn.run("main:app", host="0.0.0.0", port=8080, log_level="info")
