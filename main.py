from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import subprocess
import logging
import uvicorn
import ffmpeg
import requests
from pathlib import Path
import re
import uuid
import traceback
import mimetypes
import os
import json
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from dotenv import load_dotenv
from googleapiclient.discovery import build


def get_drive_service():
    if "GOOGLE_TOKENS_JSON" not in os.environ:
        raise RuntimeError("❌ GOOGLE_TOKENS_JSON 환경변수가 없습니다. 먼저 OAuth 인증을 완료하세요.")
    tokens = json.loads(os.environ["GOOGLE_TOKENS_JSON"])
    creds = Credentials.from_authorized_user_info(tokens)
    return build("drive", "v3", credentials=creds)



# .env 로딩 (로컬 개발 환경용)
load_dotenv()

logger = logging.getLogger("uvicorn")
logger.setLevel(logging.DEBUG)

app = FastAPI()
app.mount("/static", StaticFiles(directory="tmp"), name="static")

Path("tmp").mkdir(parents=True, exist_ok=True)

# 구글 인증 정보 및 Drive 서비스 생성
REDIRECT_URI = "https://primary-production-8af2.up.railway.app/rest/oauth2-credential"

if "GOOGLE_CREDENTIALS_JSON" in os.environ:
    credentials_data = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])
    credentials_dict = json.loads(credentials_json)
    credentials = service_account.Credentials.from_service_account_info(credentials_dict)
    service = build('drive', 'v3', credentials=credentials)
    drive_service = get_drive_service()

@app.get("/auth")
def auth():
    flow = Flow.from_client_config(
        credentials_data,
        scopes=["https://www.googleapis.com/auth/drive.readonly"],
        redirect_uri=REDIRECT_URI,
    )
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes=True,
        prompt="consent"
    )
    return {"auth_url": auth_url}

@app.get("/rest/oauth2-credential")
async def oauth_callback(request: Request):
    code = request.query_params["code"]
    flow = Flow.from_client_config(
        credentials_data,
        scopes=["https://www.googleapis.com/auth/drive.readonly"],
        redirect_uri=REDIRECT_URI,
    )
    flow.fetch_token(code=code)
    creds = flow.credentials
    token_data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": creds.scopes,
        "expiry": creds.expiry.isoformat()
    }
    print(json.dumps(token_data, indent=2))
    return {"message": "✅ 인증 완료!", "GOOGLE_TOKENS_JSON": token_data}

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

def extract_drive_id(url: str) -> str:
    match = re.search(r"/d/([a-zA-Z0-9_-]+)", url)
    if not match:
        raise ValueError("❌ 유효한 Google Drive 링크가 아닙니다.")
    return match.group(1)

def download_drive_file(file_id: str, filename: str) -> str:
    path = Path(f"tmp/{filename}")
    path.parent.mkdir(parents=True, exist_ok=True)
    request = drive_service.files().get_media(fileId=file_id)
    with open(path, "wb") as f:
        downloader = MediaIoBaseDownload(f, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
    logger.info(f"✅ 다운로드 완료: {path}")
    return str(path)

def create_video(image_path: str, audio_path: str, output_path: str):
    (
        ffmpeg
        .input(image_path, loop=1, framerate=2)
        .output(
            ffmpeg.input(audio_path),
            output_path,
            vcodec='libx264',
            acodec='aac',
            audio_bitrate='192k',
            pix_fmt='yuv420p',
            shortest=True,
            movflags='+faststart'
        )
        .run(overwrite_output=True)
    )

@app.post("/generate-video")
async def generate_one(item: QuestionItem):
    image_id = extract_drive_id(item.image_url)
    question_audio_id = extract_drive_id(item.question_url)
    answer_audio_id = extract_drive_id(item.answer_url)
    explanation_audio_id = extract_drive_id(item.explanation_url)
    background_id = extract_drive_id(item.background_url)

    image_file = download_drive_file(image_id, f"image_{image_id}.png")
    background_image_file = download_drive_file(background_id, f"background_{background_id}.png")
    audio_file = download_drive_file(question_audio_id, f"question_{question_audio_id}.mp3")
    answer_file = download_drive_file(answer_audio_id, f"answer_{answer_audio_id}.mp3")
    explanation_file = download_drive_file(explanation_audio_id, f"explanation_{explanation_audio_id}.mp3")

    output_filename = f"video_{question_audio_id}.mp4"
    output_file = f"tmp/{output_filename}"
    create_video(image_file, audio_file, output_file)

    BASE_URL = "https://primary-production-8af2.up.railway.app"
    public_video_url = f"{BASE_URL}/static/{output_filename}"

    return {
        "status": "ok",
        "video_file": public_video_url,
        "video_file_exists": Path(output_file).exists(),
        "background_fn": f"background_{background_id}.png",
        "image_fn": f"image_{image_id}.png",
        "question_fn": f"question_{question_audio_id}.mp3",
        "answer_fn": f"answer_{answer_audio_id}.mp3",
        "explanation_fn": f"explanation_{explanation_audio_id}.mp3",
        "video_output_fn": output_filename,
    }

@app.on_event("startup")
async def on_startup():
    subprocess.run(["ffmpeg", "-version"], check=True)
    logger.info("✅ FFmpeg 설치 확인됨")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8080, log_level="debug")
