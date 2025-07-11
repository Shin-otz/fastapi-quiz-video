import os
import json
import re
import io
from pathlib import Path
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2.credentials import Credentials

# ✅ dotenv 로딩 (선택)
try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass

# ✅ credentials 불러오기
if "GOOGLE_CREDENTIALS_JSON" in os.environ:
    credentials_data = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])
else:
    with open("credentials.json") as f:
        credentials_data = json.load(f)

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
TOKEN_PATH = "tokens.json"

# ✅ creds 생성 (토큰 파일 있으면 사용, 없으면 로그인)
if os.path.exists(TOKEN_PATH):
    creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
else:
    flow = Flow.from_client_config(
        credentials_data,
        scopes=SCOPES,
        redirect_uri="https://primary-production-8af2.up.railway.app/rest/oauth2-credential/callback"  # 로컬용 (웹 리디렉션)
    )
    auth_url, _ = flow.authorization_url(prompt="consent")

    print("🔐 아래 링크를 브라우저에 복사하여 로그인하세요:")
    print(auth_url)

    code = input("✅ 로그인 후, 주소창의 'code=' 뒤의 값을 붙여넣으세요: ").strip()
    flow.fetch_token(code=code)
    creds = flow.credentials

    with open(TOKEN_PATH, "w") as token_file:
        token_file.write(creds.to_json())
    print("🔒 인증 토큰 저장 완료: tokens.json")

# ✅ Google Drive API 클라이언트
drive_service = build("drive", "v3", credentials=creds)

# ✅ URL → file_id 추출
def extract_file_id(url: str) -> str:
    match = re.search(r"/d/([a-zA-Z0-9_-]+)", url)
    if not match:
        raise ValueError("❌ 유효한 Google Drive 링크가 아닙니다.")
    return match.group(1)

# ✅ 파일 다운로드
def download_file(file_id: str, filename: str) -> str:
    path = Path(f"tmp/{filename}")
    path.parent.mkdir(parents=True, exist_ok=True)

    request = drive_service.files().get_media(fileId=file_id)
    with open(path, "wb") as f:
        downloader = MediaIoBaseDownload(f, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()

    print(f"✅ 다운로드 완료: {path}")
    return str(path)

# ✅ 실행
if __name__ == "__main__":
    drive_url = "https://drive.google.com/file/d/1RNWQqHL93HAcg5N4CqmnI2VtqtXmEzDZ/view?usp=drivesdk"
    file_id = extract_file_id(drive_url)
    download_file(file_id, "bg_.png")
