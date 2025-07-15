import ffmpeg
import requests

BASE_URL = "http://127.0.0.1:8080"

# 테스트할 데이터
payload = {
    "next_text_mp3_url": "https://drive.google.com/file/d/1xT88lE9NREErwJEaZuBpXWpcJ6O310KZ/view?usp=drive_link",
    "next_bg_url": "https://drive.google.com/file/d/1vjc4FlwhjfiT6Vcb2EE1Jg0FrE3ZcFFR/view?usp=drive_link"
}

# POST 요청
res = requests.post(f"{BASE_URL}/generate-mp4_next", json=payload)

# 응답 출력
print("Status Code:", res.status_code)
print("Response JSON:", res.json())

# 생성된 mp4 링크
if res.status_code == 200:
    video_url = res.json().get("next_mp4")
    print("생성된 영상 URL:", video_url)
