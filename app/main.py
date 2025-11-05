import os
import shutil
import uuid
from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Optional

# .database, .models 등은 __init__.py 덕분에 올바르게 임포트됩니다.
from . import models, schemas, database
from .celery_worker import process_pipeline_task  # Celery 태스크 import

# --- FastAPI 앱 생성 및 DB 초기화 ---

# DB 테이블 생성 (이미 존재하면 무시)
# 이 코드는 main.py가 로드될 때 실행되어, app 시작 시 테이블을 보장합니다.
try:
    models.Base.metadata.create_all(bind=database.engine)
    print("Database tables created successfully (if not already exist).")
except Exception as e:
    print(f"Error creating database tables: {e}")

app = FastAPI(title="Async ML Pipeline API", version="0.1.0")


# DB 세션 의존성 주입 (FastAPI의 표준 방식)
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


# 업로드 디렉토리 (Docker 볼륨과 일치해야 함)
# 이 경로는 컨테이너 *내부*의 경로입니다.
UPLOAD_DIRECTORY = "/app/uploads"
# 컨테이너가 시작될 때 이 디렉토리가 없으면 생성합니다.
os.makedirs(UPLOAD_DIRECTORY, exist_ok=True)


# --- API 엔드포인트 ---

@app.on_event("startup")
async def startup_event():
    """서버 시작 시 DB 연결 확인 (간단한 핑)"""
    try:
        db = database.SessionLocal()
        db.execute("SELECT 1")
        db.close()
        print("Database connection successful!")
    except Exception as e:
        print(f"FATAL: Error connecting to database on startup: {e}")
        # 실제 운영 환경에서는 여기서 앱이 종료되도록 설정할 수 있습니다.


@app.get("/", include_in_schema=False)
async def root():
    return {"message": "Welcome to the Async ML Pipeline API. See /docs for details."}


@app.post("/api/v1/process",
          response_model=schemas.TaskResponse,
          status_code=status.HTTP_202_ACCEPTED,
          summary="Submit a new processing task")
async def submit_processing_request(
        file: UploadFile = File(..., description="PDF or Image file to process"),
        text: Optional[str] = Form(None, description="Optional text input"),
        db: Session = Depends(get_db)
):
    """
    파일(필수)과 텍스트(선택)를 받아 비동기 처리 작업을 제출합니다.

    - 파일을 서버에 저장합니다.
    - DB에 'PENDING' 상태로 작업을 기록합니다.
    - Celery 워커에게 실제 처리를 위임합니다.
    - **즉시 task_id를 반환합니다.**
    """
    try:
        # 1. 고유 ID 생성 (Task ID 및 파일명)
        task_id = str(uuid.uuid4())

        # 2. 파일 저장
        file_extension = os.path.splitext(file.filename)[1]
        if not file_extension:
            # 확장자가 없는 파일 방지
            file_extension = ".dat"

        saved_filename = f"{task_id}{file_extension}"
        file_path = os.path.join(UPLOAD_DIRECTORY, saved_filename)

        # 파일을 디스크에 씁니다 (비동기 방식 권장되나, 여기서는 기본 방식 사용)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 3. DB에 Task 생성 (상태: PENDING)
        db_task = models.Task(
            id=task_id,
            status="PENDING",
            input_file_path=file_path,  # 컨테이너 내부 경로 저장
            input_text=text
        )
        db.add(db_task)
        db.commit()
        db.refresh(db_task)

        # 4. Celery 워커에 작업 위임
        # .delay()를 호출하면 작업이 즉시 브로커(Redis)에게 전달됩니다.
        process_pipeline_task.delay(task_id, file_path, text)

        # 5. 사용자에게 Task ID 즉시 반환 (HTTP 202 Accepted)
        return {"task_id": task_id, "status": "PENDING"}

    except Exception as e:
        # 롤백
        db.rollback()
        print(f"Error submitting task: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit task: {str(e)}"
        )


@app.get("/api/v1/results/{task_id}",
         response_model=schemas.TaskStatus,
         summary="Get task status and results")
async def get_processing_status(task_id: str, db: Session = Depends(get_db)):
    """
    Task ID를 사용하여 작업 상태와 결과를 폴링(polling)합니다.
    프론트엔드에서 이 엔드포인트를 주기적으로 호출해야 합니다.
    """
    db_task = db.query(models.Task).filter(models.Task.id == task_id).first()

    if not db_task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )

    return db_task  # Pydantic이 자동으로 schemas.TaskStatus로 변환 (orm_mode=True)


```