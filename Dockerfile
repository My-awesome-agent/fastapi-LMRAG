# 1. 기본 Python 이미지
FROM python:3.10-slim

# 2. 작업 디렉토리 설정
WORKDIR /app

# 3. requirements.txt 복사 및 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. 전체 앱 코드 복사
COPY ./app /app

# 5. 파일 업로드 디렉토리 생성
# (실제 프로덕션에서는 이 디렉토리를 볼륨으로 마운트해야 합니다)
RUN mkdir -p /app/uploads

# 6. uvicorn 서버 실행 (FastAPI 앱)
# docker-compose.yml에서 command로 덮어쓸 예정이므로, 기본 CMD를 설정합니다.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]