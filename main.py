from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn
app = FastAPI()

class QuestionItem(BaseModel):
    question: str
    answer: str


@app.post("/generate-video")
async def generate_one(item: QuestionItem):
    print("질문:", item.question)
    print("정답:", item.answer)
    return {
        "status": "ok",
        "question": item.question,
        "answer": item.answer
    }


# 🔽 이 블럭이 있으면 python main.py 로 실행 가능
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)
