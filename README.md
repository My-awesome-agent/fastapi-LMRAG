FastAPI + Celery + PostgreSQL 비동기 처리 파이프라인

본 프로젝트는 FastAPI로 API 요청을 받고, 무거운 작업(ML/AI)을 Celery 워커에게 위임하여 비동기적으로 처리하는 파이프라인 아키텍처입니다. 작업의 상태와 결과는 PostgreSQL에 저장됩니다.

🚀 아키텍처

FastAPI (api 서비스):

/api/v1/process: (POST) 파일과 텍스트를 업로드받습니다.

즉시 task_id를 생성하고 DB에 PENDING 상태로 저장합니다.

Celery에게 작업을 위임하고 사용자에게 task_id를 반환합니다 (HTTP 202).

/api/v1/results/{task_id}: (GET) task_id로 작업 상태와 결과를 조회(Polling)합니다.

Redis (redis 서비스):

Celery의 메시지 브로커(Message Broker)이자 결과 백엔드(Result Backend) 역할을 합니다.

Celery (worker 서비스):

Redis를 모니터링하다가 새 작업을 받아옵니다.

DB 상태를 PROCESSING으로 변경합니다.

depth.py -> llm_summarization.py 파이프라인을 순차적으로 실행합니다.

완료되면 DB 상태를 SUCCESS (또는 FAILED)로 변경하고 결과를 저장합니다.

PostgreSQL (db 서비스):

모든 작업(Task)의 메타데이터, 상태, 최종 결과를 영구적으로 저장합니다.

🛠️ 실행 방법

1. 전제 조건

Docker

Docker Compose

2. 환경 변수 설정

.env 파일은 민감한 정보를 담고 있으며 .gitignore에 의해 Git 추적이 제외됩니다. (docker-compose.yml이 이 파일을 참조합니다.)

# .env 파일 생성
cp .env.example .env


(참고: 이 프로젝트에서는 .env 파일에 기본값을 넣었지만, 실제로는 user, password 등을 수정해야 합니다.)

3. 프로젝트 실행

프로젝트 루트 디렉토리에서 다음 명령을 실행합니다.

# Docker Compose로 모든 서비스 빌드 및 실행 (백그라운드)
docker-compose up --build -d


4. 서비스 확인

API 서버: http://localhost:8000/docs (Swagger UI)

PostgreSQL: (로컬) localhost:5432

Redis: (로컬) localhost:6379

🧪 테스트 방법

1. 작업 제출 (POST)

curl을 사용하거나 http://localhost:8000/docs의 Swagger UI를 이용하세요.

a) curl 사용 시:

(테스트용 빈 파일 dummy.pdf 생성)

touch dummy.pdf


(API 호출)

curl -X 'POST' \
  'http://localhost:8000/api/v1/process' \
  -H 'accept: application/json' \
  -H 'Content-Type: multipart/form-data' \
  -F 'file=@dummy.pdf;type=application/pdf' \
  -F 'text=이것은 선택적인 텍스트입니다'


b) 응답 (예시):

{
  "task_id": "a1b2c3d4-e5f6-7890-abcd-1234567890ab",
  "status": "PENDING"
}


2. 결과 확인 (GET)

위에서 받은 task_id를 사용하여 8초~10초 후에 결과를 조회합니다.

# {task_id}를 실제 받은 ID로 변경하세요
curl -X 'GET' \
  'http://localhost:8000/api/v1/results/{task_id}' \
  -H 'accept: application/json'


a) 처리 중일 때 응답 (예시):

{
  "task_id": "a1b2c3d4-e5f6-7890-abcd-1234567890ab",
  "status": "PROCESSING",
  "result": null,
  "error": null,
  "created_at": "2025-11-05T03:16:30.123456",
  "finished_at": null
}


b) 처리 완료 시 응답 (예시): (총 8초 시뮬레이션 후)

{
  "task_id": "a1b2c3d4-e5f6-7890-abcd-1234567890ab",
  "status": "SUCCESS",
  "result": "최종 요약 결과: {\"file_analysis\": \"complex_data_...을(를) 성공적으로 처리함.",
  "error": null,
  "created_at": "2025-11-05T03:16:30.123456",
  "finished_at": "2025-11-05T03:16:38.567890"
}


⚙️ CI/CD (GitHub Actions)

.github/workflows/ci-cd.yml 파일에 기본적인 CI/CD 파이프라인 예시가 포함되어 있습니다.

CI (Build & Test): main 브랜치로의 push 또는 pull_request 시 실행됩니다.

의존성 설치

(필요) Linter 실행 (현재 예시)

(권장) pytest 실행

CD (Deploy): main 브랜치 push가 성공적으로 CI를 통과하면 실행됩니다.

Docker Hub에 이미지를 빌드하고 푸시합니다.

SSH를 통해 프로덕션 서버에 접속하여 새 이미지를 받고 docker-compose를 재시작합니다.

주의: CD를 사용하려면 GitHub 레포지토리에 DOCKERHUB_USERNAME, DOCKERHUB_TOKEN, PROD_SERVER_HOST 등의 Secrets를 설정해야 합니다.