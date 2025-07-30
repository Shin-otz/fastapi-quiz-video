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
import mimetypes
import os
import logging
from mutagen.mp3 import MP3
from typing import List
import subprocess
import shutil
import time
import traceback
from moviepy import AudioFileClip, CompositeAudioClip, ImageClip, TextClip, CompositeVideoClip,ColorClip
import moviepy
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.video.fx.FadeIn import FadeIn
from moviepy.video.fx.FadeOut import FadeOut
from moviepy.video.fx.CrossFadeIn import CrossFadeIn
import sys
from typing import Dict, Any
import uuid, os

from urllib.parse import urlparse

from fastapi import Body
from typing import Any

# uvicorn과 같은 핸들러 사용
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout  # <- 꼭 stdout으로 지정
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

app = FastAPI()

logger.debug("HAHa ...")
logger.debug(subprocess.check_output(["ffmpeg", "-version"]).decode())
# tmp 폴더 생성
Path("tmp").mkdir(parents=True, exist_ok=True)

app = FastAPI()
app.mount("/static", StaticFiles(directory="tmp"), name="static")


# 기존 영상 생성 함수는 그대로 사용

def apply_mapping_to_format(entry: dict) -> dict:
    """
    entry: metadata + format 포함된 dict
    해당 entry의 'format' 내부의 layers에 대해 필요한 값을 채워넣음
    """
    mapping_data = entry.copy()
    format_data = mapping_data.get("format", {})
    layers = format_data.get("layers", [])

    for layer in layers:
        name = layer.get("name")
        layer_type = layer.get("type")

        if name in mapping_data:
            value = mapping_data[name]
            if layer_type == "image":
                layer["imgUrl"] = value
            elif layer_type == "text":
                layer["text"] = value
            elif layer_type == "audio":
                layer["audioUrl"] = value

    return format_data

# 엔드포인트: 비디오 생성 없이 매핑된 포맷만 반환
@app.post("/generate-from-layers")
async def generate_from_layers(entries: List[Dict[str, Any]] = Body(...)):
    results = []
    for entry in entries:
        updated_format = apply_mapping_to_format(entry)
        results.append({
            "status": "ok",
            "mappedFormat": updated_format
        })
    return results

# Step 1. 미디어 사전 다운로드 및 길이 계산
def preprocess_layers(
    layers: List[dict],
    download_cache: dict = None,
    used_files: set = None
) -> List[dict]:
    print("LAYER ***********")
    print(layers)

    if used_files is None:
        used_files = set()
    if download_cache is None:
        download_cache = {}

    for layer in layers:
        t = layer.get("type")
        layer["__duration"] = None
        layer["__actual_path"] = None

        if t == "audio":
            audio_url = layer.get("audioUrl", "")
            print("🔍 [AUDIO] 원본 URL:", audio_url)
            path = download_if_remote(audio_url, cache=download_cache, used_files=used_files)
            print("📥 다운로드된 오디오 경로:", path)

            if path and Path(path).exists():
                try:
                    layer["__actual_path"] = path
                    audio_dur = get_duration(path)
                    layer["__duration"] = (
                        float(layer.get("gapBefore", 0)) +
                        audio_dur +
                        float(layer.get("gapAfter", 0))
                    )
                    print(f"✅ 오디오 duration: {layer['__duration']}초")
                except Exception as e:
                    print("❌ 오디오 duration 계산 실패:", e)

        elif t == "text":
            mp3_url = layer.get("mp3Url", "")
            print("🔍 [TEXT] mp3 URL:", mp3_url)

            if mp3_url:
                path = download_if_remote(mp3_url, cache=download_cache, used_files=used_files)
                print("📥 다운로드된 mp3 경로:", path)

                if path and Path(path).exists():
                    try:
                        layer["__actual_path"] = path
                        mp3_dur = get_duration(path)
                        layer["__duration"] = (
                            float(layer.get("mp3PreGap", 0)) +
                            mp3_dur +
                            float(layer.get("mp3PostGap", 0))
                        )
                        print(f"✅ 텍스트 mp3 duration: {layer['__duration']}초")
                    except Exception as e:
                        print("❌ 텍스트 mp3 duration 계산 실패:", e)

        elif t == "countdown":
            layer["__duration"] = float(layer.get("countdownStart", 5))
            print(f"⏱ 카운트다운 duration: {layer['__duration']}초")

        elif "duration" in layer:
            layer["__duration"] = float(layer.get("duration", 0))
            print(f"📦 기본 duration 지정: {layer['__duration']}초")

    return layers


# Step 2. 부분 레이어 시간 정리
def calculate_partial_timings(layers: List[dict], default_duration=3.0) -> None:
    layer_map = {l["id"]: l for l in layers}
    cursor = 0

    for layer in layers:
        if layer.get("timeMode") != "부분":
            continue

        start = cursor + float(layer.get("gapBefore", 0))

        if layer.get("linkMode") == "relative" and layer.get("linkedLayerId"):
            ref = layer_map.get(layer["linkedLayerId"])
            if ref:
                anchor = ref["endTime"] if layer["relativeAnchor"] == "end" else ref["startTime"]
                start = float(anchor or 0) + float(layer.get("offset", 0))

        dur = float(layer.get("__duration") or layer.get("duration", default_duration))
        layer["startTime"] = round(start, 1)
        layer["endTime"] = round(start + dur, 1)
        layer["duration"] = round(dur, 1)

        cursor = layer["endTime"] + float(layer.get("gapAfter", 0))

# Step 3. 이미지 레이어 시간 연동 처리
def resolve_image_timings(layers: List[dict]) -> None:
    layer_map = {l["id"]: l for l in layers}

    for layer in layers:
        if layer["type"] == "image" and layer.get("timeMode") == "부분":
            s = layer_map.get(layer.get("linkedStartLayerId"))
            e = layer_map.get(layer.get("linkedEndLayerId"))
            if s and e:
                layer["startTime"] = round(s["startTime"], 1)
                layer["endTime"] = round(e["endTime"], 1)
                layer["duration"] = round(layer["endTime"] - layer["startTime"], 1)

# Step 4. 전체 duration 계산
def calculate_total_duration(layers: List[dict]) -> float:
    valid = [float(l["endTime"]) for l in layers if "endTime" in l]
    if not valid:
        return 0.0
    return max(valid)

# Step 5. full 처리
def apply_full_end_link(layers: List[dict], total_duration: float) -> None:
    for layer in layers:
        if layer.get("endLinkMode") == "full":
            offset = float(layer.get("endOffset", 0))
            layer["endTime"] = round(total_duration + offset, 1)
            layer["duration"] = round(layer["endTime"] - layer["startTime"], 1)

#Step 6. 전체 timeMode 처리
def apply_full_duration_to_all(layers: List[dict], total_duration: float) -> None:
    for layer in layers:
        if layer.get("timeMode") == "전체":
            layer["startTime"] = 0
            layer["endTime"] = total_duration
            layer["duration"] = total_duration

@app.post("/debug-timings")
async def debug_layer_timings(payload: List[Dict[str, Any]]):
    print("📦 Payload 전체:", payload)

    if not payload or "mappedFormat" not in payload[0]:
        return {"error": "❌ 잘못된 payload 형식"}

    mapped = payload[0]["mappedFormat"]
    layers = mapped.get("layers", [])

    print("🔢 레이어 수:", len(layers))
    for layer in layers:
        print(f"🧱 ID: {layer.get('id')}, Type: {layer.get('type')}, Duration: {layer.get('duration')}")

    # 여기서 타이밍 계산 실행
    updated_layers = recalculate_all_timings(layers)
    total_duration = calculate_total_duration(updated_layers)

    return {
        "totalDuration": total_duration,
        "layers": updated_layers
    }

@app.post("/generate-video-from-layer")
async def generate_video_from_layer(entries: List[Dict[str, Any]] = Body(...)):
    """
    n8n으로부터 전달받은 JSON을 기반으로 영상 생성 + 임시 파일 정리 포함
    """
    results = []
    used_files = set()
    download_cache = {}

    for entry in entries:
        try:
            print("\n🚀 [START] 영상 생성 시작")

            mapped = entry["mappedFormat"]
            layers = mapped["layers"]

            # 전체 타이밍 계산
            layers = recalculate_all_timings(
                layers,
                download_cache=download_cache,
                used_files=used_files
            )
            mapped["layers"] = layers


            # 🎬 파일명 (UUID 기반 실제 저장용)
            filename = f"video_{uuid.uuid4().hex[:6]}.mp4"
            output_path = os.path.join("tmp", filename)

            # 🎯 video_output_fn (question mp3 기반 ID 사용)
            question_url = entry.get("question_mp3") or entry.get("questionUrl", "")
            file_id = extract_drive_id_safe(question_url)
            video_output_fn = f"video_{file_id}.mp4" if file_id else ""

            # 영상 생성
            result_path = make_video_from_layers(
                mapped,
                output_path,
                download_cache=download_cache,
                used_files=used_files
            )

            # 결과 추가
            results.append({
                "status": "success",
                "videoPath": result_path,
                "filename": filename,                  # 실제 저장된 랜덤 파일명
                "video_output_fn": video_output_fn,    # 논리적 ID 기반 이름
                "duration": max(float(l.get("endTime", 0)) for l in layers),
            })

        except Exception as e:
            print(f"❌ 영상 생성 실패: {e}")
            results.append({
                "status": "error",
                "message": str(e)
            })

    # 🔥 사용된 임시 파일 삭제
    print("\n🧹 사용된 임시 파일 삭제 시작")
    for path in used_files:
        try:
            f = Path(path)
            if f.exists():
                f.unlink()
                print(f"🗑️ 삭제 완료: {f}")
        except Exception as e:
            print(f"⚠️ 삭제 실패: {path} → {e}")

    return results


def make_video_from_layers(
    mapped_format: Dict[str, Any],
    output_path: str,
    download_cache: dict = None,
    used_files: set = None
) -> str:
    layers_data = mapped_format["layers"]
    canvas_ratio = mapped_format.get("canvasRatio", "1024x768")
    canvas_width, canvas_height = map(int, canvas_ratio.split("x"))
    total_duration = max(float(l.get("endTime", 0)) for l in layers_data)
    base_clip = ColorClip((canvas_width, canvas_height), color=(255, 255, 255)).with_duration(total_duration)

    video_clips = []
    audio_clips = []

    if download_cache is None:
        download_cache = {}
    if used_files is None:
        used_files = set()

    font_path = os.path.abspath("tmp/NanumMyeongjo-YetHangul.ttf")
    if not os.path.exists(font_path):
        raise FileNotFoundError(f"❌ 폰트 파일이 존재하지 않습니다: {font_path}")

    for layer in layers_data:
        t = layer.get("type")
        start = float(layer.get("startTime", 0))
        dur = float(layer.get("duration", 0))
        x = int(layer.get("x", 0))
        y = int(layer.get("y", 0))
        w = int(layer.get("width", 100))
        h = int(layer.get("height", 50))
        opacity = float(layer.get("backgroundOpacity", 1))

        if t == "image":
            img_url = layer.get("imgUrl")
            img_path = download_if_remote(img_url, cache=download_cache, used_files=used_files)
            if img_path and os.path.exists(img_path):
                try:
                    clip = (ImageClip(img_path)
                            .resized(width=w)
                            .with_opacity(opacity)
                            .with_start(start)
                            .with_duration(dur)
                            .with_position((x, y)))
                    video_clips.append(clip)
                except Exception as e:
                    print("❌ 이미지 클립 생성 실패:", e)


        elif t == "text":
            txt = layer.get("text", "")
            font_size = int(layer.get("fontSize", 30))
            color = layer.get("color", "black")
            align = layer.get("textAlign", "left")
            vertical_align = layer.get("verticalAlign", "top")
            line_height = float(layer.get("lineHeight", 1.0))
            wrapped = wrap_text_by_width(txt, font_path, font_size, max_width=w)
            img = draw_text_with_spacing(
                wrapped,
                font_path,
                font_size,
                color,
                (w, h),
                spacing=line_height,
                align=align,
                vertical_align=vertical_align
            )
            clip = (ImageClip(np.array(img))
                    .with_start(start)
                    .with_duration(dur)
                    .with_position((x, y)))
            video_clips.append(clip)

        elif t == "countdown":
            count = int(layer.get("countdownStart", 5))
            font_size = int(layer.get("fontSize", 50))
            color = layer.get("color", "red")
            for i in range(count, 0, -1):
                img = draw_text_with_spacing(str(i), font_path, font_size, color, (w, h), spacing=1, align='center')
                tclip = (ImageClip(np.array(img))
                         .with_start(start + (count - i))
                         .with_duration(1)
                         .with_position((x, y)))
                video_clips.append(tclip)
            beep_path = f"tmp/beep_{uuid.uuid4().hex[:6]}.mp3"
            generate_beep_sequence(count, beep_path)
            audio_clips.append(AudioFileClip(beep_path).with_start(start))
            used_files.add(beep_path)

        elif t == "audio":
            audio_url = layer.get("audioUrl", "").strip()
            audio_path = download_if_remote(audio_url, cache=download_cache, used_files=used_files)
            if audio_path and os.path.exists(audio_path):
                aclip = AudioFileClip(audio_path).with_start(start)
                audio_clips.append(aclip)

    final_audio = CompositeAudioClip(audio_clips) if audio_clips else None
    final_video = CompositeVideoClip([base_clip] + video_clips).with_audio(final_audio)
    output_path = os.path.abspath(output_path)
    final_video.write_videofile(output_path, fps=25, codec='libx264', audio_codec='aac')

    final_video.close()
    if final_audio:
        final_audio.close()

    return output_path



def check_ffmpeg_drawtext():
    try:
        # ffmpeg 필터 목록에서 drawtext가 있는지 확인
        result = subprocess.run(
            ["ffmpeg", "-filters"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        filters_output = result.stdout

        if "drawtext" in filters_output:
            logger.info("✅ ffmpeg drawtext 필터 지원 확인됨.")
        else:
            logger.error("❌ ffmpeg drawtext 필터가 없습니다! Dockerfile을 수정하거나 빌드를 확인하세요.")
    except FileNotFoundError:
        logger.error("❌ ffmpeg 명령을 찾을 수 없습니다. ffmpeg가 설치되어 있는지 확인하세요.")
    except Exception as e:
        logger.exception(f"❌ ffmpeg 필터 확인 중 오류 발생: {e}")

def generate_beep_sequence(beep_seconds: int, output_path: str):
    from pydub import AudioSegment
    from pydub.generators import Sine

    beep = Sine(1000).to_audio_segment(duration=300).apply_gain(-3)   # 0.3초 삐
    silence = AudioSegment.silent(duration=700)                       # 0.7초 쉼
    one_beep = beep + silence
    countdown_beep = one_beep * beep_seconds
    countdown_beep.export(output_path, format="mp3")
    return output_path

def recalculate_all_timings(
    layers: List[dict],
    default_duration: float = 3.0,
    download_cache: dict = None,
    used_files: set = None
) -> List[dict]:
    """
    전체 타이밍 계산 파이프라인 (preprocess → timings → total duration → full 처리)
    """
    if download_cache is None:
        download_cache = {}
    if used_files is None:
        used_files = set()

    print("\n🔍 [STEP 1] 미디어 사전 다운로드 및 길이 계산")
    layers = preprocess_layers(layers, download_cache=download_cache, used_files=used_files)

    print("\n🧮 [STEP 2] '부분' 레이어 시간 정리")
    calculate_partial_timings(layers, default_duration)

    print("\n🖼️ [STEP 3] 이미지 레이어 시간 연동")
    resolve_image_timings(layers)

    print("\n⏱️ [STEP 4] 전체 영상 총 시간 계산")
    total_duration = calculate_total_duration(layers)
    print(f"📏 전체 영상 길이: {total_duration:.1f}초")

    print("\n🔁 [STEP 5] endLinkMode = full 처리")
    apply_full_end_link(layers, total_duration)

    print("\n🌐 [STEP 6] timeMode = 전체 처리")
    apply_full_duration_to_all(layers, total_duration)

    print("\n✅ [RESULT] 레이어별 타이밍 정보")
    for i, l in enumerate(layers):
        print(f"{i+1:2}. 🧩 {l.get('type','?')} | {l.get('name','(no-name)'):<15} "
              f"→ ⏱ {l.get('startTime', '?')} ~ {l.get('endTime', '?')}  "
              f"(dur: {l.get('duration', '?')})")

    return layers


def recalculate_layer_timings_for_backend(layers: List[dict], default_duration: float = 3.0) -> List[dict]:
    """
    React에서 사용한 시간 정렬 로직을 Python으로 포팅한 버전.
    """
    round1 = lambda v: round(v, 1)
    new_layers = [l.copy() for l in layers]
    layer_map = {l["id"]: l for l in new_layers}

    cursor = 0
    for layer in new_layers:
        if layer["type"] in {"text", "countdown", "audio"} and layer["timeMode"] == "부분":
            base_start = cursor + float(layer.get("gapBefore", 0))

            if layer.get("linkMode") == "relative" and layer.get("linkedLayerId"):
                base = layer_map.get(layer["linkedLayerId"])
                if base:
                    anchor = base["endTime"] if layer.get("relativeAnchor") == "end" else base["startTime"]
                    base_start = float(anchor or 0) + float(layer.get("offset", 0))

            dur = float(layer.get("duration") or default_duration)

            if layer["type"] == "text" and layer.get("mp3Url", "").strip():
                dur = (
                    float(layer.get("mp3PreGap", 0)) +
                    float(layer.get("duration", default_duration)) +
                    float(layer.get("mp3PostGap", 0))
                )

            layer["startTime"] = round1(base_start)
            layer["endTime"] = round1(base_start + dur)
            layer["duration"] = round1(layer["endTime"] - layer["startTime"])
            cursor = layer["endTime"] + float(layer.get("gapAfter", 0))

    for layer in new_layers:
        if layer["type"] == "image" and layer["timeMode"] == "부분":
            s = layer_map.get(layer.get("linkedStartLayerId"))
            e = layer_map.get(layer.get("linkedEndLayerId"))
            if s and e:
                layer["startTime"] = round1(s["startTime"])
                layer["endTime"] = round1(e["endTime"])
                layer["duration"] = round1(layer["endTime"] - layer["startTime"])

    total_duration = max(float(l.get("endTime", 0)) for l in new_layers)

    for layer in new_layers:
        if layer.get("endLinkMode") == "full":
            layer["endTime"] = round1(total_duration + float(layer.get("endOffset", 0)))
            layer["duration"] = round1(layer["endTime"] - layer["startTime"])  # ✅ 이걸로 변경

    for layer in new_layers:
        if layer["timeMode"] == "전체":
            layer["startTime"] = 0
            layer["endTime"] = total_duration
            layer["duration"] = total_duration

    return new_layers



def draw_text_with_spacing(
    text: str,
    font_path: str,
    font_size: int,
    color: str,
    size: tuple,
    spacing: float = 1.0,
    align: str = "left",
    vertical_align: str = "top"
):
    width, height = size
    font = ImageFont.truetype(font_path, font_size)
    lines = text.split("\n")

    line_height = int(font_size * spacing)
    total_text_height = line_height * len(lines)

    # 수직 정렬
    if vertical_align in ("center", "middle"):
        y = (height - total_text_height) // 2
    elif vertical_align == "bottom":
        y = height - total_text_height
    else:
        y = 0  # top

    img = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)

    for line in lines:
        line_width = draw.textlength(line, font=font)
        if align == "center":
            x = (width - line_width) // 2
        elif align == "right":
            x = width - line_width
        else:
            x = 0

        draw.text((x, y), line, font=font, fill=color)
        y += line_height

    return img



def wrap_text(text, max_chars=28):
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

def wrap_text_by_width(text, font_path, font_size, max_width):
    """
    주어진 텍스트를 font 기준 max_width 안에 맞게 줄바꿈 처리
    """
    font = ImageFont.truetype(font_path, font_size)
    dummy_img = Image.new("RGB", (10, 10))
    draw = ImageDraw.Draw(dummy_img)

    words = text.strip().split()
    lines = []
    current = ""

    for word in words:
        test_line = f"{current} {word}".strip()
        width = draw.textlength(test_line, font=font)
        if width <= max_width:
            current = test_line
        else:
            if current:
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
    explanation: str
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
def extract_drive_id_safe(url: str) -> str:
    if not url or not isinstance(url, str):
        return str(uuid.uuid4())[:8]  # fallback for None or non-str
    match = re.search(r"/d/([a-zA-Z0-9_-]+)", url)
    if match:
        return match.group(1)
    return str(uuid.uuid4())[:8]

def convert_drive_url(url: str) -> str:
    # Google Drive 보기 링크 → 직접 다운로드 링크 변환
    match = re.search(r"/d/([a-zA-Z0-9_-]+)", url)
    if not match:
        return url  # 변환 실패하면 원본 반환
    file_id = match.group(1)
    return f"https://drive.google.com/uc?export=download&id={file_id}"
def download_if_remote(
    url: str,
    cache: dict = None,
    used_files: set = None
) -> str:
    if not url:
        return ""

    # Google Drive 변환
    if "drive.google.com" in url:
        url = convert_drive_url(url)

    if cache is not None and url in cache:
        print(f"♻️ [HIT] 캐시 재사용: {url} → {cache[url]}")
        return cache[url]

    # 파일 확장자 추출
    ext = os.path.splitext(urlparse(url).path)[-1]
    if not ext or len(ext) > 6:
        ext = ".bin"

    # Google Drive ID를 파일명으로
    unique_name = extract_drive_id(url) or uuid.uuid4().hex[:6]
    local_path = f"tmp/{unique_name}{ext}"

    # 이미 존재하면 재사용
    if Path(local_path).exists():
        print(f"♻️ [HIT] 파일 존재 재사용: {local_path}")
        if cache is not None:
            cache[url] = local_path
        if used_files is not None:
            used_files.add(local_path)
        return local_path

    try:
        print(f"📥 다운로드 시작: {url}")
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            with open(local_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        print(f"✅ 다운로드 완료: {local_path}")

        if cache is not None:
            cache[url] = local_path
        if used_files is not None:
            used_files.add(local_path)

        return local_path

    except Exception as e:
        print(f"❌ 다운로드 실패: {url} → {e}")
        return ""


def make_video_from_mapped_format(payload: List[Dict[str, Any]], output_path: str):
    entry = payload[0]  # 첫 번째 항목만 처리
    format_data = entry["mappedFormat"]
    canvas_w, canvas_h = map(int, format_data.get("canvasRatio", "1280x720").split("x"))
    layers = format_data.get("layers", [])

    base = ColorClip((canvas_w, canvas_h), color=(255,255,255))
    total_duration = max(float(l.get("endTime", 0)) for l in layers)
    base = base.with_duration(total_duration)

    video_clips = []
    audio_clips = []

    for layer in layers:
        typ = layer.get("type")
        start = float(layer.get("startTime", 0))
        duration = float(layer.get("duration", 0))
        x, y = int(layer.get("x", 0)), int(layer.get("y", 0))
        w, h = int(layer.get("width", 100)), int(layer.get("height", 50))
        opacity = float(layer.get("backgroundOpacity", 1))

        if typ == "image":
            img_path = download_if_remote(layer.get("imgUrl", ""))
            if img_path:
                clip = (ImageClip(img_path)
                        .resized(width=w)
                        .with_opacity(opacity)
                        .with_start(start)
                        .with_duration(duration)
                        .with_position((x, y)))
                video_clips.append(clip)

        elif typ == "text":
            txt = layer.get("text", "")
            fontsize = int(layer.get("fontSize", 30))
            color = layer.get("color", "#000000")
            clip = (TextClip(txt, fontsize=fontsize, color=color, size=(w,h), method='caption')
                    .with_start(start)
                    .with_duration(duration)
                    .with_position((x, y)))
            video_clips.append(clip)

        elif typ == "audio":
            audio_path = download_if_remote(layer.get("audioUrl", ""))
            if audio_path:
                acl = AudioFileClip(audio_path).with_start(start)
                audio_clips.append(acl)

    final_audio = CompositeAudioClip(audio_clips) if audio_clips else None
    final_video = CompositeVideoClip([base] + video_clips).with_audio(final_audio)
    output_path = os.path.abspath(output_path)
    final_video.write_videofile(output_path, fps=25, codec="libx264", audio_codec="aac")

    # Clean up
    for l in layers:
        if "imgUrl" in l:
            p = Path(l["imgUrl"])
            if str(p).startswith("tmp/") and p.exists():
                p.unlink()

    return output_path

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


def download_file_tmp2(url: str, filename: str) -> str:
    if "drive.google.com" in url:
        url = convert_drive_url(url)

    r = requests.get(url)
    r.raise_for_status()

    path = Path(f"tmp2/{filename}")
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with open(path, "wb") as f:
            f.write(r.content)
    return str(path)


@app.get("/check-list")
def check_list(filename: str):
    file_path = Path(f"tmp/{filename}_list.txt")
    if file_path.exists():
        return FileResponse(path=str(file_path), media_type="text/plain")
    else:
        return {"error": "list.txt 파일이 존재하지 않음"}


def download_drive_file(url: str, dest: Path) -> str:
    # URL에서 ID 추출
    file_id = url.split("/d/")[1].split("/")[0]
    direct_url = f"https://drive.google.com/uc?export=download&id={file_id}"
    r = requests.get(direct_url)
    dest.write_bytes(r.content)
    return str(dest)


def drive_url_to_direct_link(url: str) -> str:
    # 예: https://drive.google.com/file/d/1abcDEF/view?usp=sharing
    match = re.search(r"/d/([a-zA-Z0-9_-]+)", url)
    if not match:
        raise ValueError("Invalid Google Drive URL")
    file_id = match.group(1)
    return f"https://drive.google.com/uc?export=download&id={file_id}"


class VideoMergeRequest(BaseModel):
    sheet_name: str
    merged_video_name: str
    videos: List[str]  # ✅ 중요: 문자열 리스트로 정의


def download_mp4(url: str, filename: str) -> str:
    direct_url = drive_url_to_direct_link(url)
    TMP_DIR = Path("tmp")
    path = TMP_DIR / filename
    with requests.get(direct_url, stream=True) as r:
        r.raise_for_status()
        with open(path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    while True:
        if os.path.exists(path) and os.path.getsize(path) > 1000:
            break
    time.sleep(0.5)
    return str(path)

def merge_videos_with_fade(file_paths: list[str], output_name: str, fade_duration: float = 1.0) -> str:
    TMP_DIR = Path("tmp")
    TMP_DIR.mkdir(exist_ok=True)

    # 첫 번째 파일을 기준으로 시작
    output_path = TMP_DIR / f"{output_name}.mp4"

    if len(file_paths) < 2:
        raise ValueError("최소 두 개 이상의 영상이 필요합니다.")

    # 순차적으로 xfade로 합치기
    current = file_paths[0]
    for idx, next_video in enumerate(file_paths[1:], start=1):
        tmp_out = TMP_DIR / f"{output_name}_step{idx}.mp4"

        # xfade는 두개의 입력만 받으므로, 반복적으로 이어 붙임
        # fade_duration만큼 교차 전환
        command = [
            "ffmpeg",
            "-y",
            "-i", current,
            "-i", next_video,
            "-filter_complex",
            f"[0:v][1:v]xfade=transition=fade:duration={fade_duration}:offset=0[v];"
            f"[0:a][1:a]acrossfade=d={fade_duration}[a]",
            "-map", "[v]",
            "-map", "[a]",
            "-c:v", "libx264",
            "-crf", "18",
            "-preset", "veryfast",
            "-c:a", "aac",
            "-b:a", "192k",
            str(tmp_out)
        ]
        subprocess.run(command, check=True)

        # 다음 단계 입력으로 사용
        current = str(tmp_out)

    # 최종 결과물
    final_output = TMP_DIR / f"{output_name}_final.mp4"
    Path(current).rename(final_output)
    return str(final_output)

def get_duration(path: str) -> float:
    info = ffmpeg.probe(path)
    return float(info['format']['duration'])

def merge_videos_ffmpeg2(file_paths: list[str], output_name: str, fade_duration: float = 1.0) -> str:
    TMP_DIR = Path("tmp")
    TMP_DIR.mkdir(exist_ok=True)

    # 경로를 / 형식으로
    file_paths = [str(Path(p).resolve().as_posix()) for p in file_paths]

    current = file_paths[0]
    for idx, next_file in enumerate(file_paths[1:], start=1):
        tmp_out = TMP_DIR / f"{output_name}_step{idx}.mp4"
        tmp_out = tmp_out.resolve().as_posix()

        dur = get_duration(current)
        offset = max(dur - fade_duration, 0)

        filter_complex = (
            f"[0:v][1:v]xfade=transition=fade:duration={fade_duration}:offset={offset}[v];"
            f"[0:a][1:a]acrossfade=d={fade_duration}[a]"
        )

        cmd = [
            "ffmpeg", "-y",
            "-i", current,
            "-i", next_file,
            "-filter_complex", filter_complex,
            "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-crf", "18", "-preset", "fast",
            "-c:a", "aac", "-b:a", "192k",
            tmp_out
        ]
        subprocess.run(cmd, check=True)
        current = tmp_out

    final_output = TMP_DIR / f"{output_name}_final.mp4"
    Path(current).rename(final_output)
    return str(final_output)

def merge_videos_ffmpeg(file_paths: list[str], output_name: str) -> str:
    TMP_DIR = Path("tmp")
    TMP_DIR.mkdir(exist_ok=True)

    list_path = TMP_DIR / f"{output_name}_list.txt"

    del_files = []

    # ✅ 절대경로 사용
    with open(list_path, "w", encoding="utf-8") as f:
        for file_path in file_paths:
            abs_path = Path(file_path).resolve().as_posix()
            f.write(f"file '{abs_path}'\n")
            del_files.append(abs_path) # 나중에 지우기

    file_num = str((len(del_files)+1)//2).zfill(2)

    output_file = f"{output_name}_{file_num}.mp4"
    output_path = TMP_DIR / f"{output_name}_{file_num}.mp4"

    del_files.append(list_path)  # 나중에 지우기
    """
    command = [
        "ffmpeg",
        "-f", "concat",
        "-safe", "0",
        "-y",
        "-i", str(list_path.resolve().as_posix()),  # 절대경로로 바꿔줌
        "-c", "copy",
        str(output_path.resolve().as_posix())
    ]

    command = [
        "ffmpeg",
        "-f", "concat",
        "-safe", "0",
        "-y",
        "-i", str(list_path),
        "-c:v", "libx264",
        "-c:a", "aac",
        "-strict", "experimental",
        str(output_path)
    ]
    """
    command = [
        "ffmpeg",
        "-f", "concat",
        "-safe", "0",
        "-y",
        "-i", str(list_path),
        "-c", "copy",
        "-c:a", "aac",
        str(output_path.resolve().as_posix())
    ]

    subprocess.run(command, check=True)

    # Delete tmp folder
    for del_file in del_files:
        file_path = Path(del_file)
        if file_path.exists():
            file_path.unlink()
            print(f"✅ 파일 삭제 완료: {file_path}")
        else:
            print(f"⚠ 파일이 존재하지 않습니다: {file_path}")

    return {"status": "ok", "output": output_file}

@app.post("/merge-videos")
async def merge_videos(payload: List[VideoMergeRequest]):
    results = []

    for item in payload:
        sheet = item.sheet_name
        merged_name = item.merged_video_name
        video_urls = item.videos

        print(f"[{sheet}] '{merged_name}' 병합 시작: {len(video_urls)}개 영상")

        # 1. 각 URL에서 mp4 다운로드
        file_paths = []
        for i, url in enumerate(video_urls):
            filename = f"{merged_name}_{i}.mp4"
            try:
                path = download_mp4(url, filename)
                file_paths.append(path)
            except Exception as e:
                print(f"다운로드 실패: {url}, 에러: {e}")
                results.append({
                    "sheet": sheet,
                    "merged_video_name": merged_name,
                    "video_count": len(video_urls),
                    "status": "fail",
                    "error": str(e)
                })
                continue
        print("----")
        print(file_paths)

        # 2. FFmpeg로 병합
        try:
            print("----")
            print(file_paths)
            output_path = merge_videos_ffmpeg(file_paths, merged_name)
            status = "success"
        except Exception as e:
            print(f"병합 실패: {e}")
            output_path = file_paths
            status = "fail"

        # 3. 결과 저장
        results.append({
            "sheet": sheet,
            "merged_video_name": merged_name,
            "video_count": len(video_urls),
            "merged_path": output_path,
            "list_path": video_urls,
            "ffmpeg": shutil.which("ffmpeg"),
            "status": status
        })

    return {"result": results}


class NextItem(BaseModel):
    next_text_mp3_url: str
    next_bg_url: str


@app.post("/generate-mp4_next")
async def generate_next(item: NextItem):
    # 🔽 각 URL에 대해 고유 ID 기반 파일명 생성
    next_audio_id = extract_drive_id(item.next_text_mp3_url)
    background_id = extract_drive_id(item.next_bg_url)

    # 🔽 파일 다운로드
    next_mp3_file = download_file(item.next_text_mp3_url, f"next_mp3_{next_audio_id}.mp3")
    background_image_file = download_file(item.next_bg_url, f"next_bg_{background_id}.png")

    # 🔽 출력 파일명
    output_filename = f"next_{next_audio_id}.mp4"
    output_file = f"tmp/{output_filename}"

    data_ = {
        "next_mp3": next_mp3_file,
        "next_bg_image": background_image_file,
    }

    make_next_moviepy_mp4(data_, output_file)

    # create_video(data_, (output_file))

    BASE_URL = "https://primary-production-8af2.up.railway.app"
    public_video_url = f"{BASE_URL}/static/{output_filename}"

    return {
        "status": "ok",
        "next_mp3": next_mp3_file,
        "next_bg_image": background_image_file,
        "next_mp4": output_file
    }


def make_next_moviepy_mp4(data_, output_path):
    next_mp3_path = os.path.abspath(data_["next_mp3"])
    bgimage_path = os.path.abspath(data_["next_bg_image"])
    output_path = os.path.abspath(output_path)

    # 오디오
    question_a = AudioFileClip(next_mp3_path)
    final_audio = CompositeAudioClip([question_a]).with_fps(44100)

    # 이미지 (moviepy 2.1.2 기준 with_resize 사용)

    base_clip = ImageClip(bgimage_path).with_duration(final_audio.duration)

    # 합성
    final_clip = base_clip.with_audio(final_audio)

    # 출력
    final_clip.write_videofile(
        output_path,
        fps=25,
        codec='libx264',
        audio_codec='aac'
    )
    print(f"✅ 생성 완료 (moviepy): {output_path}")

    del_files = []
    del_files.append(next_mp3_path)
    del_files.append(bgimage_path)

    # Delete tmp folder
    for del_file in del_files:
        file_path = Path(del_file)
        if file_path.exists():
            file_path.unlink()
            print(f"✅ 파일 삭제 완료: {file_path}")
        else:
            print(f"⚠ 파일이 존재하지 않습니다: {file_path}")

    return {"status": "ok", "output": output_path}


def make_next_mp4(data_, output_path):
    next_mp3_path = data_["next_mp3"]
    bgimage_path = data_["next_bg_image"]

    try:
        # 이미지 입력 (반복), 프레임레이트 1fps 지정
        image_input = ffmpeg.input(bgimage_path, loop=1)

        question_a = AudioFileClip(next_mp3_path)
        final_audio = CompositeAudioClip([question_a]).with_fps(44100)
        output_audio_path = os.path.join("tmp", f"next_final.mp3")
        final_audio.write_audiofile(output_audio_path)
        # 오디오 입력
        audio_input = ffmpeg.input(output_audio_path)

        # 스케일 필터 적용
        base = image_input.filter('scale', 1080, 720)

        ffmpeg.output(
            base, audio_input,
            output_path,

            vcodec='libx264',
            acodec='aac',
            audio_bitrate='192k',
            pix_fmt='yuv420p',
            shortest=None,
            movflags='+faststart'
        ).run(overwrite_output=True)

        print(f"✅ 생성 완료: {output_path}")

    except ffmpeg.Error as e:
        err_msg = e.stderr.decode() if e.stderr else str(e)
        print(f"❌ ffmpeg 에러 발생:\n{err_msg}")
        raise RuntimeError(f"ffmpeg error: {err_msg}")

@app.get("/")
def hello():
    logger.info("👋 INFO 로그 작동!")
    logger.debug("🐛 DEBUG 로그 작동!")
    return {"message": "hello"}


# @app.exception_handler(Exception)
# async def general_exception_handler(request, exc):
#    logger.error(f"예외 발생: {traceback.format_exc()}")
#    return JSONResponse(status_code=500, content={"message": "Internal server error."})
def create_text_image(
        text,
        font_path,
        font_size,
        color,
        size,
        key_term=None,
        align='center',
        spacing=1,
        line_spacing=5
):
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(font_path, font_size)

    # 키워드 강조 리스트
    highlight_terms = list(dict.fromkeys(key_term.split(','))) if key_term else []

    lines = text.split('\n')
    y_offset = 0
    space_width = draw.textlength(" ", font=font)  # 공백 한 글자 너비

    for line in lines:
        words = line.split(' ')
        # 총 너비 계산
        total_width = 0
        for wi, word in enumerate(words):
            for ch in word:
                total_width += draw.textlength(ch, font=font) + spacing
            if wi < len(words) - 1:
                total_width += space_width
        # 정렬
        if align == 'center':
            x_start = (size[0] - total_width) // 2
        elif align == 'right':
            x_start = size[0] - total_width
        else:
            x_start = 0

        # 단어 출력
        for wi, word in enumerate(words):
            for idx, char in enumerate(word):
                is_highlight = False
                for term in highlight_terms:
                    tstart = word.find(term)
                    tend = tstart + len(term)
                    if tstart != -1 and tstart <= idx < tend:
                        draw.text((x_start, y_offset), char, font=font, fill="blue")
                        is_highlight = True
                        break
                if not is_highlight:
                    draw.text((x_start, y_offset), char, font=font, fill=color)
                x_start += draw.textlength(char, font=font) + spacing
            if wi < len(words) - 1:
                x_start += space_width  # 단어 사이 공백 추가
        y_offset += font.getbbox("A")[3] - font.getbbox("A")[1] + line_spacing
    return img

def make_quiz_video_with_title_top_moviepy(data_, output_path):
    try:
        font_path = os.path.abspath('tmp/NanumMyeongjo-YetHangul.ttf')

        # 경로
        question_audio = os.path.abspath(data_["question_audio"])
        answer_audio = os.path.abspath(data_["answer_audio"])
        explanation_audio = os.path.abspath(data_["explanation_audio"])
        beef_audio = os.path.abspath(data_["beef_audio"])
        bgimage_path = os.path.abspath(data_["background_image"])
        image_path = os.path.abspath(data_["image_"])

        # 텍스트
        question_text = data_["question_text"]
        hint_text = data_["hint_text"]
        answer_text = data_["answer_text"]
        explanation_text = data_["explanation"]
        key_term_text = data_["key_term"] + "," + answer_text

        # 오디오
        question_a = AudioFileClip(question_audio)
        answer_a = AudioFileClip(answer_audio).with_start(question_a.duration + 1 + 5)
        beef_a = AudioFileClip(beef_audio).with_start(question_a.duration + 1)
        explanation_a = AudioFileClip(explanation_audio).with_start(
            question_a.duration + 1 + 5 + answer_a.duration + 1
        )
        final_audio = CompositeAudioClip([question_a, answer_a, beef_a, explanation_a]).with_fps(44100)

        # 배경
        base_clip = ImageClip(bgimage_path).with_duration(final_audio.duration)
        text_clips = []

        # ======== 제목 ========
        img_title = create_text_image("한국사 퀴즈", font_path, 38, "black", (540, 100),
                                      None, align='center', spacing=1)
        title_clip = ImageClip(np.array(img_title)).with_position(("center", 12)).with_duration(final_audio.duration)
        text_clips.append(title_clip)

        # ======== 문제 ========
        img_question = create_text_image(wrap_text(question_text), font_path, 30, "black", (900, 300),
                                         key_term=key_term_text, align='left', spacing=0, line_spacing=15)
        question_clip = ImageClip(np.array(img_question)).with_position((190, 115)).with_duration(final_audio.duration)
        text_clips.append(question_clip)

        # ======== 추가 이미지 (문제 아래) ========
        extra_img_clip = (
            ImageClip(image_path)
                .resized(width=360)  # ✅ 정확한 메서드 이름
                .with_position((580, 150))
                .with_duration(final_audio.duration)
                .with_opacity(0.5)
                .with_effects([
                CrossFadeIn(3),  # 0.5초 페이드인
            ])
        )

        text_clips.append(extra_img_clip)

        # ======== 힌트 ========
        img_hint = create_text_image(f"힌트: {hint_text}", font_path, 30, "blue", (500, 150),
                                     None, align='left')
        hint_clip = ImageClip(np.array(img_hint)).with_position((300, 250)) \
            .with_start(question_a.duration + 4).with_duration(2)
        text_clips.append(hint_clip)

        # ======== 카운트다운 ========
        for i in range(5, 0, -1):
            img_count = create_text_image(str(i), font_path, 80, "red", (500, 200),
                                          None, align='center')
            countdown_clip = ImageClip(np.array(img_count)).with_position("center") \
                .with_start(question_a.duration + 1 + (5 - i)).with_duration(1)
            text_clips.append(countdown_clip)

        # ======== 정답 ========
        img_answer = create_text_image(f"정답: {answer_text}", font_path, 30, "black", (500, 150),
                                       None, align='left')
        answer_clip = ImageClip(np.array(img_answer)).with_position((300, 350)) \
            .with_start(question_a.duration + 1 + 5) \
            .with_duration(final_audio.duration - (question_a.duration + 1 + 5))
        text_clips.append(answer_clip)

        # ======== 해설 ========
        img_expl = create_text_image(wrap_text(explanation_text), font_path, 28, "black", (900, 300),
                                     key_term=key_term_text, align='left', spacing=0, line_spacing=15)
        explanation_clip = ImageClip(np.array(img_expl)).with_position((200, 510)) \
            .with_start(question_a.duration + 1 + 5 + answer_a.duration + 1) \
            .with_duration(explanation_a.duration)
        text_clips.append(explanation_clip)

        # ======== 합성 및 출력 ========
        final_clip = CompositeVideoClip([base_clip] + text_clips).with_audio(final_audio)
        output_path = os.path.abspath(output_path)
        final_clip.write_videofile(output_path, fps=25, codec='libx264', audio_codec='aac')

        print(f"✅ 생성 완료 (moviepy): {output_path}")

        # ======== 임시파일 삭제 ========
        for del_file in [question_audio, answer_audio, explanation_audio, bgimage_path, image_path]:
            file_path = Path(del_file)
            if file_path.exists():
                file_path.unlink()
                print(f"🗑️ 파일 삭제 완료: {file_path}")
            else:
                print(f"⚠️ 파일이 존재하지 않습니다: {file_path}")

        return {"status": "ok", "output": output_path}

    except Exception as e:
        logger.error("❌ [MoviePy/FFmpeg] 에러 타입: %s", type(e))
        logger.error("❌ [MoviePy/FFmpeg] 에러 메시지: %s", str(e))
        logger.error("❌ [MoviePy/FFmpeg] 전체 스택:\n%s", traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"🎥 moviepy/ffmpeg 에러: {str(e)}")

def make_quiz_video_with_title_top(data_, output_path):
    # 🔥 모든 경로를 절대 경로로 변환
    font = os.path.abspath('tmp/NanumMyeongjo-YetHangul.ttf')

    question_audio = os.path.abspath(data_["question_audio"])
    answer_audio = os.path.abspath(data_["answer_audio"])
    explanation_audio = os.path.abspath(data_["explanation_audio"])
    beef_audio = os.path.abspath(data_["beef_audio"])
    bgimage_path = os.path.abspath(data_["background_image"])
    image_path = os.path.abspath(data_["image_"])

    output_path = os.path.abspath(output_path)

    question_text = data_["question_text"]
    hint_text = data_["hint_text"]
    answer_text = data_["answer_text"]
    explanation_text = data_["explanation"]
    key_term = data_["key_term"]
    ID = data_["ID"]

    # 오디오 길이 정보
    q_length = MP3(question_audio).info.length
    a_length = MP3(answer_audio).info.length
    e_length = MP3(explanation_audio).info.length

    # 오디오 클립 로딩 및 시작 시간 설정
    question_a = AudioFileClip(question_audio)
    answer_a = AudioFileClip(answer_audio).with_start(question_a.duration + 1 + 5)
    beef_a = AudioFileClip(beef_audio).with_start(question_a.duration + 1)
    explanation_a = AudioFileClip(explanation_audio).with_start(
        question_a.duration + 1 + 5 + answer_a.duration + 1
    )

    final_audio = CompositeAudioClip([question_a, answer_a, beef_a, explanation_a]).with_fps(44100)
    output_audio_path = os.path.abspath(os.path.join("tmp", f"final_{ID}.mp3"))
    final_audio.write_audiofile(output_audio_path)

    try:
        image_input = ffmpeg.input(bgimage_path, loop=1, framerate=25)
        audio_input = ffmpeg.input(output_audio_path)
        base = image_input.filter('scale', 1080, 720)

        # drawtext 추가
        video = base.drawtext(
            text='한국사 퀴즈',
            fontfile=font,
            fontsize=33,
            fontcolor='black',
            x='(w-text_w)/2',
            y='16',
            box=1,
            boxcolor='black@0.0',
            boxborderw=10,
            enable='gte(t,0)'
        )

        video = video.drawtext(
            text=wrap_text(question_text),
            fontfile=font,
            fontsize=30,
            fontcolor='black',
            x='200',
            y='120',
            box=1,
            boxcolor='black@0.0',
            boxborderw=10,
            enable='gte(t,0)'
        )

        video = video.drawtext(
            text=f"힌트: {hint_text}",
            fontfile=font,
            fontsize=30,
            fontcolor='blue',
            x='(w-text_w)/2',
            y='250',
            box=1,
            boxcolor='black@0.01',
            boxborderw=10,
            enable=f'between(t,{question_a.duration + 4},{question_a.duration + 1 + 5})'
        )

        for i in range(5, 0, -1):
            start = question_a.duration + 1 + (5 - i)
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

        video = video.drawtext(
            text=f"정답: {answer_text}",
            fontfile=font,
            fontsize=30,
            fontcolor='black',
            x='(w-text_w)/2',
            y='250',
            box=1,
            boxcolor='black@0.0',
            boxborderw=10,
            enable=f'gte(t,{question_a.duration + 1 + 5})'
        )

        video = video.drawtext(
            text=wrap_text(explanation_text),
            fontfile=font,
            fontsize=30,
            fontcolor='black',
            x='150',
            y='320',
            box=1,
            boxcolor='black@0.0',
            boxborderw=10,
            enable=f'gte(t,{question_a.duration + 1 + 5 + answer_a.duration + 1})'
        )

        (
            ffmpeg
            .output(
                video,
                audio_input,
                output_path,
                vcodec='libx264',
                acodec='aac',
                audio_bitrate='192k',
                pix_fmt='yuv420p',
                shortest=None,
                movflags='+faststart'
            )
            .run(
                overwrite_output=True,
                capture_stdout=True,
                capture_stderr=True
            )
        )
        print(f"✅ 생성 완료: {output_path}")

    except ffmpeg.Error as e:
        # raw bytes 출력
        logger.error(f"[STDERR RAW] {e.stderr}")
        # 디코드 후 출력
        logger.error(f"[STDERR DECODED]\n{e.stderr.decode(errors='ignore')}")
        raise HTTPException(status_code=500, detail=f"ffmpeg 에러: {e.stderr.decode(errors='ignore')}")


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
        "question_text": item.question,
        "hint_text": item.hint,
        "key_term": item.key_term,
        "answer_text": item.answer,
        "explanation": item.explanation,
        "ID": question_audio_id
    }

    result = make_quiz_video_with_title_top_moviepy(data_, output_file)
    if isinstance(result, dict) and result.get("status") == "error":
        return result  # ffmpeg 에러 내용을 그대로 클라이언트에 반환

    # create_video(data_, (output_file))

    BASE_URL = "https://primary-production-8af2.up.railway.app"
    public_video_url = f"{BASE_URL}/static/{output_filename}"

    return {
        "status": "ok",
        "ID": question_audio_id,
        "question_audio": question_file,
        "answer_audio": answer_file,
        "explanation_audio": explanation_file,
        "beef_audio": "tmp/countdown_beep.mp3",
        "image_": image_file,
        "background_image": background_image_file,
        "question_text": item.question,
        "hint_text": item.hint,
        "key_term": item.key_term,
        "answer_text": item.answer,
        "explanation": item.explanation,
        "video_output_fn": output_filename,
        "video_file_exists": Path(output_file).exists(),
        "Image": Path(background_image_file).exists(),
        "MP3": Path(question_file).exists(),
        "beef_mp3": Path("tmp/countdown_beep.mp3").exists()
    }



@app.post("/delete_file")
def delete_file(data: FileRequest):
    deleted = []
    not_found = []
    errors = []

    try:
        file_path = os.path.join('tmp', data.filename)
        deleted.append(file_path)

        # 파일 삭제
        for del_file in deleted:
            path_obj = Path(del_file)
            if path_obj.exists():
                try:
                    path_obj.unlink()
                    logger.info(f"✅ 파일 삭제 완료: {path_obj}")
                except Exception as e:
                    err_msg = f"❌ 파일 삭제 중 오류: {path_obj}, {e}"
                    logger.error(err_msg)   # 🚀 Railway 콘솔에도 찍힘
                    errors.append({"file": str(path_obj), "error": str(e)})
            else:
                not_found.append(str(path_obj))
                logger.warning(f"⚠ 파일이 존재하지 않음: {path_obj}")

    except Exception as e:
        # 최상위 예외 처리
        err_msg = f"❌ delete_file 핸들러 내부 오류: {e}"
        logger.error(err_msg)
        errors.append({"file": data.filename, "error": str(e)})

    return {
        "deleted": deleted,
        "not_found": not_found,
        "errors": errors
    }

class FileDeleteRequest(BaseModel):
    filenames: List[str]


@app.post("/delete_files")
def delete_files(request: FileDeleteRequest):
    FOLDER_PATH = "tmp"
    deleted = []
    not_found = []
    errors = []

    for fname in request.filenames:
        file_path = os.path.join(FOLDER_PATH, fname)
        deleted.append(file_path)

    # Delete tmp folder
    for del_file in deleted:
        file_path = Path(del_file)
        if file_path.exists():
            file_path.unlink()
            print(f"✅ 파일 삭제 완료: {file_path}")
        else:
            not_found=f"{file_path}이 없습니다."
            print(f"⚠ 파일이 존재하지 않습니다: {file_path}")

    return {
        "deleted": deleted,
        "not_found": not_found,
        "errors": errors
    }


@app.get("/get-media")
def get_media(filename: str):
    file_path = f"{filename}"

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
    file_path = Path(f"{filename}")
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
    file_path = Path(f"{filename}")

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
    video_path = Path(f"{filename}")
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
    print(moviepy.__version__)
    logger.info("✅ FFmpeg 설치 확인됨, 서버 시작!")
    check_ffmpeg_drawtext()

"""
if __name__ == "__main__":
    question_file = download_file_tmp2("https://drive.google.com/file/d/10dM1fc_hSJa9Y4-9vaSxRSjh2I0Twgs8/view?usp=drive_link", "question.mp3")
    answer_file = download_file_tmp2("https://drive.google.com/file/d/1ONaATr2Z5dbD2VlOeDG4TbOsjOOyjPrc/view?usp=drive_link", "answer.mp3")
    explanation_file = download_file_tmp2("https://drive.google.com/file/d/19df-6d0SGO5K6i2jIzmaDy-_xmB6lm2B/view?usp=drive_link", "explanation.mp3")
    background_file = download_file_tmp2("https://drive.google.com/file/d/1vjc4FlwhjfiT6Vcb2EE1Jg0FrE3ZcFFR/view?usp=drive_link", "background.png")
    image_file = download_file_tmp2("https://drive.google.com/file/d/1EXR7malg374i7SW_GfxPVXDZhQ1gkkt2/view?usp=drive_link", "image.png")

    test_data = {
        "question_audio": "tmp2/question.mp3",
        "answer_audio": "tmp2/answer.mp3",
        "explanation_audio": "tmp2/explanation.mp3",
        "beef_audio": "tmp2/countdown_beep.mp3",
        "background_image": "tmp2/background.png",
        "image_": "tmp2/image.png",
        "question_text": "세종대왕이 만든 문자는?",
        "hint_text": "ㅎㄱ",
        "answer_text": "한글",
        "explanation": "세종대왕은 훈민정음을 창제하여 백성이 쉽게 배우도록 했다.",
        "key_term": "훈민정음"
    }

    output_path = "tmp2/test_output.mp4"
    make_quiz_video_with_title_top(test_data, output_path)

    print("✅ 테스트 영상 생성 완료:", output_path)

    logger.info("Starting ...")
    uvicorn.run("main:app", host="0.0.0.0", port=8080, log_level="info")
"""

if __name__ == "__main__":
    logger.info("Starting ...")
    # 퀴즈 영상 병합 테스트용 Google Drive URL 목록
    """
    urls = [
        "https://drive.google.com/file/d/1HqCiVP0_zLEQjWfqVY7gBJZgJQfHuh6C/view?usp=drive_link",
        "https://drive.google.com/file/d/1YqErlJEnU-2c6532tIRQR_VrIzoacxJj/view?usp=drive_link",
        "https://drive.google.com/file/d/1nV5qi9XOa7R7UnCEyF3RLySPV-qwGR1G/view?usp=drive_link",
        "https://drive.google.com/file/d/1pjPGZ6DbNODsmV7plflqGrs_dm8x3rvj/view?usp=drive_link",
        "https://drive.google.com/file/d/1vP_W6K1t4swnaAeYmMfT9zZqjScSVMSh/view?usp=drive_link"
    ]


    file_paths = []
    for i, url in enumerate(urls):
        filename = f"local_merge_{i}.mp4"
        try:
            print(url)
            path = download_mp4(url, filename)
            file_paths.append(path)
        except Exception as e:
            print(f"❌ 다운로드 실패: {url}, 에러: {e}")

    # 병합 테스트
    try:
        merged_path = merge_videos_ffmpeg(file_paths, "local_test_merged")
        print("✅ 병합 완료:", merged_path)
    except Exception as e:
        print("❌ 병합 실패:", e)
    """
    # FastAPI 실행
    uvicorn.run("main:app", host="0.0.0.0", port=8080, log_level="info")

