from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional

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

# ⬇️ 여기서 "data" 키를 포함하는 구조로 받아들임
class QuizPayload(BaseModel):
    data: List[QuizEntry]

@app.post("/generate-video")
async def generate_video(payload: QuizPayload):
    for entry in payload.data:
        print(f"🎬 Generating video for row {entry.row_number}: {entry.Question_text}")
        # generate_video_ffmpeg(entry)
    return {"status": "processing started", "count": len(payload.data)}
