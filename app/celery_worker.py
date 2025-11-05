import os
import time
from celery import Celery
from sqlalchemy.orm import Session
from datetime import datetime

# DB 및 시뮬레이션 모듈 import
# __init__.py 파일이 있으므로 .database, .models 등이 올바르게 동작합니다.
from . import database, models
from .core import depth, llm_summarization

# --- Celery 앱 설정 ---

# 환경 변수에서 브로커 및 백엔드 URL 로드 (docker-compose에서 주입)
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://redis:6379/0")

celery_app = Celery(
    "worker",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND
)

# Celery 설정
celery_app.conf.update(
    task_track_started=True,  # 작업 시작 추적
    broker_connection_retry_on_startup=True  # 시작 시 브로커 재연결 시도
)


# --- Celery 태스크 정의 ---

@celery_app.task(name="process_pipeline_task")
def process_pipeline_task(task_id: str, file_path: str, text: str | None):
    """
    FastAPI로부터 작업을 받아 실제 파이프라인을 실행하는 메인 태스크
    (이 코드는 Celery 워커 프로세스에서 실행됩니다)
    """

    # [중요] 워커에서 새 DB 세션 생성
    # FastAPI와 다른 프로세스이므로 세션을 공유할 수 없습니다.
    db: Session = database.SessionLocal()

    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        print(f"[Worker] Task {task_id} not found in DB.")
        db.close()
        return

    try:
        # 2. DB에서 Task 객체 가져오기 및 상태 'PROCESSING'으로 변경
        print(f"[Worker] Starting task {task_id}...")
        task.status = "PROCESSING"
        db.commit()

        # 3. [시뮬레이션] depth.py 실행
        # (실제로는 여기서 file_path와 text를 사용합니다)
        depth_result = depth.run_depth_analysis(file_path, text)

        # 4. [시뮬레이션] llm_summarization.py 실행
        final_result = llm_summarization.run_llm_summary(depth_result)

        # 5. 성공: DB에 결과 및 상태 'SUCCESS' 업데이트
        task.status = "SUCCESS"
        task.result = final_result  # JSON이나 텍스트 저장
        task.finished_at = datetime.utcnow()
        print(f"[Worker] Finished task {task_id} successfully.")

    except Exception as e:
        # 6. 실패: DB에 오류 메시지 및 상태 'FAILED' 업데이트
        # 롤백을 대비해 DB 객체를 다시 조회하거나 세션을 초기화할 수 있지만,
        # 여기서는 간단히 오류 메시지만 기록합니다.
        db.rollback()  # 오류 발생 시 이전 커밋(PROCESSING) 이후 변경사항 롤백
        task = db.query(models.Task).filter(models.Task.id == task_id).first()  # 객체 다시 가져오기

        print(f"[Worker] Task {task_id} failed: {str(e)}")
        task.status = "FAILED"
        task.error_message = str(e)
        task.finished_at = datetime.utcnow()

    finally:
        # 7. DB 세션 커밋 및 종료
        db.commit()
        db.close()
        print(f"[Worker] Session closed for task {task_id}.")