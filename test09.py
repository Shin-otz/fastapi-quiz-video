import requests


# 테스트할 데이터
data={
    "question_type": "주관식",
    "topic": "고구려",
    "question": "고구려를 건국한 사람은 누구인가요?",
    "key_term": "고구려,시조",
    "hint": "ㅈㅁ",
    "answer": "주몽",
    "explanation": "고구려는 고대 한국의 삼국 중 하나로, 시조는 주몽(또는 성기왕)입니다. 그는 부여에서 탈출하여 고구려를 건국했습니다.",
    "background_url": "https://drive.google.com/file/d/1vjc4FlwhjfiT6Vcb2EE1Jg0FrE3ZcFFR/view?usp=drive_link",
    "image_url": "https://drive.google.com/file/d/1X8c1VRQ27kRUYsY-q785hOBxsCF2Xkyw/view?usp=drive_link",
    "question_url": "https://drive.google.com/file/d/1ILN6dpESyFja1mwwd0L4jQEnK3oqxRwF/view?usp=drive_link",
    "answer_url": "https://drive.google.com/file/d/16lJVMjY8THylAeGRxmrxiYiU0ROoDGWb/view?usp=drive_link ",
    "explanation_url": "https://drive.google.com/file/d/1onzJ5SgDEDnLqjvu1jhRi-FbwfrVum1U/view?usp=drive_link"
}

BASE_URL = "http://127.0.0.1:8080"
# POST 요청
url = f"{BASE_URL}/generate-video"

# POST 요청 보내기
response = requests.post(url, json=data)

# 응답 확인
if response.status_code == 200:
    print("Success!")
    print("Response JSON:", response.json())
else:
    print("Failed with status code:", response.status_code)
    print("Response:", response.text)
