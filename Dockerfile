# 1. 베이스 이미지 선택
FROM python:3.10-slim

# [추가] Python이 'app' 모듈을 찾을 수 있도록 영구적인 환경 변수 설정
ENV PYTHONPATH=/app

# 2. 작업 디렉토리 설정
WORKDIR /app

# 3. requirements.txt 복사 및 설치
# (빌드 속도 향상을 위해 requirements.txt만 먼저 복사)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. 전체 앱 코드 복사
# (.dockerignore에 명시된 파일/폴더를 제외하고 현재 디렉토리(.)의 모든 것을
#  컨테이너의 /app 디렉토리로 복사)
COPY . .

# 5. (삭제) uvicorn 명령은 docker-compose.yml에서 실행하므로 여긴 필요 없음
# EXPOSE 8000