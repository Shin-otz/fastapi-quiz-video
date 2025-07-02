from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn
app = FastAPI()

class QuestionItem(BaseModel):
    question_type: str
    topic: str
    question: str
    keyword: str
    hint: str
    answer: str
    background_url: str
    image_url: str
    question_url: str
    answer_url: str
    explanation_url: str


@app.post("/generate-video")
async def generate_one(item: QuestionItem):
    print("질문:", item.question)
    print("정답:", item.answer)
    return {
        "status": "ok",
        "question": item.question,
        "answer": item.answer,
        "background_url": item.background_url,
        "hint": item.hint
    }


# 🔽 이 블럭이 있으면 python main.py 로 실행 가능
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)
