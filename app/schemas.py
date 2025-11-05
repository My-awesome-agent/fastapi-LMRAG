from pydantic import BaseModel
from datetime import datetime
from typing import Optional

# Pydantic 모델: API의 입출력 데이터 형식을 정의하고 검증합니다.
# Pydantic은 FastAPI의 핵심 기능입니다.

class TaskResponse(BaseModel):
    """작업 제출 시 즉시 반환되는 응답"""
    task_id: str
    status: str

    class Config:
        orm_mode = True # SQLAlchemy 모델(models.Task)과 호환되도록 설정

class TaskStatus(BaseModel):
    """작업 상태 폴링 시 반환되는 응답"""
    task_id: str
    status: str
    result: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime
    finished_at: Optional[datetime] = None

    class Config:
        orm_mode = True # SQLAlchemy 모델과 호환