from fastapi import FastAPI, Request
from pydantic import BaseModel
from typing import List, Optional
import json

app = FastAPI()

class QuizEntry(BaseModel):
    row_number: Optional[int]
    Question_type: str
    Topic: str
    Difficulty: Optional[str]
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
    use: Optional[str]

@app.post("/generate-video")
async def generate_video(request: Request):
    data = await request.json()

    # Check if the payload uses "body" key
    if "body" in data and isinstance(data["body"], list):
        entries = [QuizEntry(**entry) for entry in data["body"]]
    else:
        return {"error": "Invalid format: expected `body` with a list of quiz items."}

    for entry in entries:
        print(f"🎬 Generating video for row {entry.row_number}: {entry.Question_text}")
        # generate_video_ffmpeg(entry)  # your real function

    return {"status": "processing started", "count": len(entries)}
