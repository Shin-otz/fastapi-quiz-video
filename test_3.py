import ffmpeg
import requests

BASE_URL = "http://127.0.0.1:8080"

# 테스트할 데이터
payload = {
    "next_text_mp3_url": "https://drive.google.com/file/d/1xT88lE9NREErwJEaZuBpXWpcJ6O310KZ/view?usp=drive_link",
    "next_bg_url": "https://drive.google.com/file/d/1vjc4FlwhjfiT6Vcb2EE1Jg0FrE3ZcFFR/view?usp=drive_link"
}

url = f"{BASE_URL}/generate-mp4_next"

# POST 요청 보내기
response = requests.post(url, json=payload)

# 응답 확인
if response.status_code == 200:
    print("Success!")
    print("Response JSON:", response.json())
else:
    print("Failed with status code:", response.status_code)
    print("Response:", response.text)
