import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# .env 파일에서 환경 변수 로드 (docker-compose에서 주입하지만, 로컬 테스트 시 유용)
load_dotenv()

# docker-compose.yml의 'environment'에서 이 변수를 설정합니다.
# 기본값을 제공하여 로컬 테스트 시에도 오류가 나지 않도록 할 수 있습니다.
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://user:password@localhost:5432/appdb")

# SQLAlchemy 엔진 생성
engine = create_engine(
    DATABASE_URL
)

# DB 세션 생성을 위한 SessionLocal 클래스
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 모델 클래스들이 상속받을 Base 클래스
Base = declarative_base()