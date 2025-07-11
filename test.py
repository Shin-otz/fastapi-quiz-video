import requests
from pathlib import Path
import re

def convert_drive_url(url: str) -> str:
    """
    Google Drive 공유 링크에서 file ID 추출
    """
    match = re.search(r"/d/([a-zA-Z0-9_-]+)", url)
    if not match:
        raise ValueError("Google Drive URL에서 파일 ID를 찾을 수 없습니다.")
    return match.group(1)

def download_file_from_drive(url: str, filename: str, output_dir="tmp") -> str:
    file_id = convert_drive_url(url)
    session = requests.Session()

    download_url = "https://drive.google.com/uc?export=download"

    # Step 1: 첫 요청 (확인 토큰 필요 여부 확인)
    response = session.get(download_url, params={'id': file_id}, stream=True)

    # Step 2: confirm 토큰이 필요한 경우 추출
    confirm_token = None
    for key, value in response.cookies.items():
        if key.startswith("download_warning"):
            confirm_token = value

    if confirm_token:
        response = session.get(
            download_url,
            params={'id': file_id, 'confirm': confirm_token},
            stream=True
        )

    # Step 3: 파일 저장
    path = Path(output_dir) / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        for chunk in response.iter_content(32768):
            if chunk:
                f.write(chunk)

    return str(path)

download_file_from_drive(
    "https://drive.google.com/file/d/10dM1fc_hSJa9Y4-9vaSxRSjh2I0Twgs8/view?usp=drive_link",
    "question.mp3"
)