import requests


# 테스트할 데이터
data=[{
        "sheet_name":
            "1탄",
        "merged_video_name":
            "Merged_1탄",
        "videos":
            [
                "https://drive.google.com/file/d/149JShMbWr0hH4eUVng3KhBL4N42j6muv/view?usp=drive_link",
                "https://drive.google.com/file/d/1vF4MbWl0W6g-Eyu1cWBeFDt_j_Ncl2XG/view?usp=drive_link",
                "https://drive.google.com/file/d/1YrJcd3Pf9ihipb5pFrU9K78MQHFn3ZfD/view?usp=drive_link",
                "https://drive.google.com/file/d/1vF4MbWl0W6g-Eyu1cWBeFDt_j_Ncl2XG/view?usp=drive_link",
                "https://drive.google.com/file/d/1OiMWZv5pJ-oBoSq95AV7XXKYnhSSH7xJ/view?usp=drive_link",
                "https://drive.google.com/file/d/1vF4MbWl0W6g-Eyu1cWBeFDt_j_Ncl2XG/view?usp=drive_link",
                "https://drive.google.com/file/d/1WbT3yPVnXzjzvp5ID_RbVio7oRpquVOf/view?usp=drive_link"
            ]
    }]


BASE_URL = "http://127.0.0.1:8080"
# POST 요청
url = f"{BASE_URL}/merge-videos"

# POST 요청 보내기
response = requests.post(url, json=data)

# 응답 확인
if response.status_code == 200:
    print("Success!")
    print("Response JSON:", response.json())
else:
    print("Failed with status code:", response.status_code)
    print("Response:", response.text)
