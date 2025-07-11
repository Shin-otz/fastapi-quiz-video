from moviepy import TextClip

def make_highlighted_text(
    text,
    font='Arial-Bold',
    fontsize=60,
    color='white',
    bg_color='black',
    padding=10
):
    """배경색이 있는 강조 텍스트 클립 생성"""
    return TextClip(
        txt=text,
        fontsize=fontsize,
        font=font,
        color=color,
        bg_color=bg_color,
        print_cmd=False,
        padding=padding
    )
