import subprocess
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn
import ffmpeg
import requests
from pathlib import Path
import re
import uuid
import mimetypes
import os
import logging
from mutagen.mp3 import MP3
from moviepy import *
from utils.text_highlight import make_highlighted_text
from utils.fonts import get_font

# uvicorn 로거 설정
logger = logging.getLogger("uvicorn")
logger.setLevel(logging.DEBUG)

app = FastAPI()

logger.debug("HAHa ...")

# tmp 폴더 생성
Path("tmp").mkdir(parents=True, exist_ok=True)

app = FastAPI()
app.mount("/static", StaticFiles(directory="tmp"), name="static")

def wrap_text(text, max_chars=22):
    """
    입력 텍스트가 너무 길면 강제로 줄바꿈(\n) 추가
    기본값: 18글자 넘으면 줄바꿈 (대략 가로 30%)
    """
    words = text.strip().split()
    lines = []
    current = ""

    for word in words:
        if len(current + " " + word) <= max_chars:
            current += " " + word if current else word
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)

    return '\n'.join(lines)


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

def make_quiz_video_with_title_top(data_,output_path):
    font = r'NanumMyeongjo-YetHangul.ttf'

    question_audio = data_["question_audio"]
    answer_audio = data_["answer_audio"]
    explanation_audio = data_["explanation_audio"]
    beef_audio = data_["beef_audio"]
    bgimage_path = data_["background_image"]
    image_path = data_["image_"]

    question_text = data_["question_text"]

    q_length = (MP3(question_audio).info.length)
    a_length = (MP3(answer_audio).info.length)
    e_length = (MP3(explanation_audio).info.length)

    question_a=AudioFileClip(question_audio)
    answer_a = AudioFileClip(answer_audio).set_start(question_a.duration+1+5)
    beef_a = AudioFileClip(beef_audio).set_start(question_a.duration+1)
    explanation_a = AudioFileClip(explanation_audio).set_start(question_a.duration+1+5+answer_a.duration+0.1)

    final_audio = CompositeAudioClip([question_a,answer_a,beef_a,explanation_a]).set_fps(44100)
    final_audio.write_audiofile(r"tmp/final_.mp3")

    try:
        image_input = ffmpeg.input(bgimage_path, loop=1)
        audio_input = ffmpeg.input(r"tmp/final_.mp3")
        base = image_input.filter('scale', 1080, 720)

        # 0. 제목 항상 상단 고정
        video = base.drawtext(
            text='분석 방법',
            fontfile=font,
            fontsize=25,
            fontcolor='black',
            x='(w-text_w)/2',
            y='20',
            box=1,
            boxcolor='black@0.0',
            boxborderw=10,
            enable='gte(t,0)'
        )

        # 1. 문제
        video = video.drawtext(
            text=wrap_text(question_text),
            fontfile=font,
            fontsize=28,
            fontcolor='black',
            #x='(w-text_w)/2',
            x='200',
            y='120',
            box=1,
            boxcolor='black@0.0',
            boxborderw=10,
            enable='gte(t,0.5)'
        )

        # 2. 힌트
        video = video.drawtext(
            text="힌트: ㅂㅎㄱㅅ",
            fontfile=font,
            fontsize=42,
            fontcolor='yellow',
            x='(w-text_w)/2',
            y='250',
            box=1,
            boxcolor='black@0.5',
            boxborderw=10,
            enable=f'between(t,{question_a.duration+4},{question_a.duration+1+5})'
        )

        # 3. 카운트다운
        for i in range(5, 0, -1):
            start = question_a.duration+1 + (5 - i)
            end = start + 1
            video = video.drawtext(
                text=str(i),
                fontfile=font,
                fontsize=80,
                fontcolor='red',
                x='(w-text_w)/2',
                y='(h-text_h)/2',
                box=1,
                boxcolor='black@0.0',
                boxborderw=20,
                enable=f'between(t,{start},{end})'
            )

        # 4. 정답
        video = video.drawtext(
            text="Answer",
            fontfile=font,
            fontsize=42,
            fontcolor='cyan',
            x='(w-text_w)/2',
            y='250',
            box=1,
            boxcolor='black@0.5',
            boxborderw=10,
            #enable=f'between(t,{question_a.duration+1+5},{question_a.duration+1+5+answer_a.duration+explanation_a.duration+0.1})'
            enable=f'gte(t,{question_a.duration+1+5})'
        )

        video = video.drawtext(
            text=wrap_text("해설"),
            fontfile=font,
            fontsize=42,
            fontcolor='cyan',
            x='150',
            y='320',
            box=1,
            boxcolor='black@0.5',
            boxborderw=10,
            enable=f'gte(t,{question_a.duration+1+5+answer_a.duration})'
        )

        (
            ffmpeg
            .output(
                video, audio_input,
                output_path,
                vcodec='libx264',
                acodec='aac',
                audio_bitrate='192k',
                pix_fmt='yuv420p',
                shortest=None,
                movflags='+faststart'
            )
            .run(overwrite_output=True)
        )

        print(f'생성 완료: {output_path}')

    except ffmpeg.Error as e:
        print(e)
        print(f'❌ ffmpeg 에러:{e.stderr.decode()}')
@app.post("/generate-video")
async def generate_one(item: QuestionItem):
    logger.debug(f"질문: {item.question}")
    logger.debug(f"정답: {item.answer}")

    # 🔽 각 URL에 대해 고유 ID 기반 파일명 생성
    image_id = extract_drive_id(item.image_url)
    question_audio_id = extract_drive_id(item.question_url)
    answer_audio_id = extract_drive_id(item.answer_url)
    explanation_audio_id = extract_drive_id(item.explanation_url)
    background_id = extract_drive_id(item.background_url)

    # 🔽 파일 다운로드
    image_file = download_file(item.image_url, f"image_{image_id}.png")
    question_file = download_file(item.question_url, f"question_{question_audio_id}.mp3")
    answer_file = download_file(item.answer_url, f"answer_{answer_audio_id}.mp3")
    explanation_file = download_file(item.explanation_url, f"explanation_{explanation_audio_id}.mp3")
    background_image_file = download_file(item.background_url, f"background_{background_id}.png")

    # 🔽 출력 파일명
    output_filename = f"video_{question_audio_id}.mp4"
    output_file = f"tmp/{output_filename}"

    data_ = {
        "question_audio": question_file,
        "answer_audio": answer_file,
        "explanation_audio": explanation_file,
        "beef_audio": "tmp/countdown_beep.mp3",
        "image_": image_file,
        "background_image": background_image_file,
        "question_text": item.question
    }

    make_quiz_video_with_title_top(data_, output_file)

#    create_video((background_image_file), (audio_file), (output_file))

    BASE_URL = "https://primary-production-8af2.up.railway.app"
    public_video_url = f"{BASE_URL}/static/{output_filename}"

    return {
        "status": "ok",
        "question_audio": question_file,
        "answer_audio": answer_file,
        "explanation_audio": explanation_file,
        "beef_audio": "tmp/countdown_beep.mp3",
        "image_": image_file,
        "background_image": background_image_file,
        "question_text": item.question,
        "video_file": public_video_url,
        "video_file_exists": Path(output_file).exists(),
        "question": item.question,
        "answer": item.answer,
        "hint": item.hint,
        "key_term": item.key_term,
        "video_output_fn":output_filename,
        "bg_fn2" : background_image_file,
        "Image": Path(background_image_file).exists(),
        "MP3": Path(question_file).exists()
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
