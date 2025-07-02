from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
import uvicorn

app = FastAPI()


class QuestionItem(BaseModel):
    question: str
    answer: str


@app.post("/generate-questions")
async def generate_questions(items: List[QuestionItem]):
    for i, item in enumerate(items):
        print(f"질문 {i + 1}: {item.question}")
        print("정답:", item.answer)
        print("---")

    return {
        "status": "received",
        "count": len(items),
        "questions": [item.question for item in items]
    }


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=808git 0, reload=True)

# 🔽 이 블럭이 있으면 python main.py 로 실행 가능
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)
