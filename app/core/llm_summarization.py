import time
import json


def run_llm_summary(depth_result: str) -> str:
    """
    [시뮬레이션]
    두 번째 알고리즘 (llm_summarization.py)
    depth.py의 결과물(JSON 문자열)을 받아 요약합니다.
    """

    print(f"LLM [Task]: '{depth_result}' 요약 시작...")

    try:
        # depth.py의 결과가 JSON 문자열이라고 가정하고 파싱
        data = json.loads(depth_result)
        input_summary = f"file {data.get('file_analysis')} and text {data.get('text_input')}"
    except Exception:
        input_summary = "malformed depth result"

    # 3초간 LLM이 요약하는 척 시뮬레이션
    time.sleep(3)

    print("LLM [Task]: 요약 완료.")

    # 최종 결과물 (사용자에게 보여줄 요약 텍스트)
    return f"최종 요약 결과: {input_summary}...(을)를 성공적으로 처리하고 요약했습니다."