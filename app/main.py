import os
import shutil
import uuid
import time  # DB 재시도를 위해 time 모듈 추가
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Optional
from contextlib import asynccontextmanager
from sqlalchemy.exc import OperationalError
from fastapi.middleware.cors import CORSMiddleware # CORS 임포트

# .database, .models 등은 __init__.py 덕분에 올바르게 임포트됩니다.
from . import models, schemas, database
from .celery_worker import process_pipeline_task  # Celery 태스크 import

from .models import Task

# --- FastAPI 앱 생성 ---
app = FastAPI(title="Async ML Pipeline API", version="0.1.0")

# --- [추가] CORS 미들웨어 설정 ---
# Failed to fetch 오류를 해결합니다.
origins = [
    "http://localhost",
    "http://localhost:8000",
    "http://127.0.0.1",
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,       # 허용할 출처 (브라우저가 접속하는 주소)
    allow_credentials=True,    # 쿠키 허용 여부
    allow_methods=["*"],       # 모든 HTTP 메소드 허용 (GET, POST, OPTIONS 등)
    allow_headers=["*"],       # 모든 HTTP 헤더 허용
)

# --- DB 초기화 (Startup Event) ---
# [수정] UndefinedTable 오류를 해결하기 위해,
# 서버 시작 시 DB가 준비될 때까지 재시도하며 테이블을 생성합니다.
@app.on_event("startup")
async def startup_event():
    """
    서버 시작 시 DB 연결을 확인하고 테이블을 생성합니다.
    DB가 준비될 때까지 재시도합니다. (총 5회 시도)
    """
    print("FastAPI app starting up...")

    db_connected = False
    retries = 5

    while not db_connected and retries > 0:
        try:
            print("Attempting to connect to database...")
            # 1. DB 세션 생성 시도 (연결 확인)
            db = database.SessionLocal()
            db.execute("SELECT 1")  # 간단한 쿼리로 연결 핑
            db.close()
            db_connected = True
            print("Database connection successful!")

            # 2. 테이블 생성 (연결 성공 시에만 실행)
            print("Creating database tables (if not already exist)...")
            models.Base.metadata.create_all(bind=database.engine)
            print("Database tables created successfully.")

        except Exception as e:
            print(f"Error connecting to database or creating tables: {e}")
            retries -= 1
            print(f"Retrying... {retries} attempts left.")
            time.sleep(5)  # 5초 대기 후 재시도

    if not db_connected:
        print("FATAL: Could not connect to the database after several attempts. Exiting.")
        # 실제 운영 환경에서는 여기서 앱이 강제 종료되도록 할 수 있습니다.


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

@app.get("/", include_in_schema=False)
async def root():
    return {"message": "Welcome to the Async ML Pipeline API. See /docs for details."}


@app.post("/api/v1/process",
          response_model=schemas.TaskResponse, # POST 응답 모델
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
            # 확장자가 없는 파일 방지 (예: .pdf, .jpg)
            file_extension = ".dat"

        saved_filename = f"{task_id}{file_extension}"
        file_path = os.path.join(UPLOAD_DIRECTORY, saved_filename)

        # 파일을 디스크에 씁니다
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
        process_pipeline_task.delay(task_id, file_path, text)

        # 5. 사용자에게 Task ID 즉시 반환 (HTTP 202 Accepted)
        # schemas.TaskResponse와 일치하는 반환값
        return {"task_id": task_id, "status": "PENDING"}

    except Exception as e:
        # 롤백
        db.rollback()
        print(f"Error submitting task: {e}")
        # [수정] 에러 로그를 더 명확하게
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit task. Internal error: {str(e)}"
        )


@app.get("/api/v1/results/{task_id}",
         response_model=schemas.TaskStatus, # GET 응답 모델
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

    # [수JSON] schemas.py의 'error_message' 필드와 일치하도록 수정
    return schemas.TaskStatus(
        id=db_task.id,
        status=db_task.status,
        input_file_path=db_task.input_file_path, # 스키마에 맞게 필드 추가
        input_text=db_task.input_text,         # 스키마에 맞게 필드 추가
        result=db_task.result,
        error_message=db_task.error_message,  # 'error=' -> 'error_message='
        created_at=db_task.created_at,
        finished_at=db_task.finished_at
    )