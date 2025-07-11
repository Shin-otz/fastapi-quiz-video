from pydub import AudioSegment
from pydub.generators import Sine
import os

def generate_beep_sequence(file_path):
    beep = Sine(1000).to_audio_segment(duration=300).apply_gain(-3)   # 1000Hz, 0.3초
    silence = AudioSegment.silent(duration=700)                       # 0.7초 쉬기

    # 삐 + 쉼 → 1초짜리 beep
    one_beep = beep + silence

    # 5번 반복
    countdown_beep = one_beep * 5

    # 저장
    countdown_beep.export(file_path, format="mp3")
    print(f"(저장 완료: {file_path}")

base_dir = r"tmp"
file_path=os.path.join(base_dir,'countdown_beep.mp3')
# 실행
generate_beep_sequence(file_path)