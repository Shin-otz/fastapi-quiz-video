from fastapi import FastAPI, Request
from pydantic import BaseModel
from typing import List, Optional
import os

app = FastAPI()

class QuizEntry(BaseModel):
    row_number: Optional[int]
    Question_type: str
    Topic: str
    Difficulty_: Optional[str]
    Question_text: str
    Keyword: Optional[str]
    Hint: Optional[str]
    Answer: str
    explanation: str
    question_url: Optional[str]
    answer_url: Optional[str]
    explanation_url: Optional[str]
    Image_file_url: Optional[str]
    Image_describe: Optional[str]
    correct_answer_: Optional[str]
    question_mp3: Optional[str]
    answer_mp3: Optional[str]
    explanation_mp3: Optional[str]
    images_file: Optional[str]

@app.post("/generate-video")
async def generate_video(entries: List[QuizEntry]):
    for entry in entries:
        print(f"🎬 Generating video for row {entry.row_number}: {entry.Question_text}")
        # 여기서 FFmpeg 영상 생성 함수 호출
        # generate_video_ffmpeg(entry)
    return {"status": "processing started", "count": len(entries)}
