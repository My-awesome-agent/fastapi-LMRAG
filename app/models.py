from sqlalchemy import Column, String, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID  # Postgresql의 UUID 타입
import uuid  # Python의 UUID 모듈
from datetime import datetime
from .database import Base  # database.py의 Base 클래스 임포트


class Task(Base):
    """
    작업의 상태와 결과를 저장하는 PostgreSQL 테이블 모델
    """
    __tablename__ = "tasks"

    # 고유 Task ID
    # id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4) # 네이티브 UUID 타입
    # 호환성을 위해 String으로 변경 (main.py에서 str(uuid.uuid4())로 생성)
    id = Column(String, primary_key=True, index=True)

    # 작업 상태 (PENDING, PROCESSING, SUCCESS, FAILED)
    status = Column(String, index=True, nullable=False, default="PENDING")

    # 입력 값
    input_file_path = Column(String, nullable=False)
    input_text = Column(Text, nullable=True)

    # 결과 및 오류
    result = Column(Text, nullable=True)  # JSON 문자열이나 텍스트 저장
    error_message = Column(Text, nullable=True)

    # 시간 기록
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at = Column(DateTime, nullable=True)