# ORBIT — 1인 개발자 프로젝트 관제 허브

멀티 프로젝트를 운영하는 솔로 개발자를 위한 통합 관제 대시보드.
프로젝트, 에이전트, 타임라인, 세션, 커밋, 비용, AI 할일을 한 곳에서 관리합니다.

## 스택

| 영역 | 기술 |
|------|------|
| Backend | Python 3.12 + FastAPI + SQLAlchemy (async) |
| Frontend | Jinja2 + HTMX + Alpine.js + Tailwind CSS |
| Chart | Chart.js (트렌드, 스파크라인, 도넛) |
| Database | PostgreSQL 16 (AWS RDS, SSH 터널) |
| AI | GPT-4o (할일 추천) |
| Infra | Docker Compose (로컬) |

## 주요 기능

- **대시보드** — 크로스 프로젝트 요약 위젯 + 28일 활동 트렌드 차트 + 프로젝트별 스파크라인
- **에이전트 모니터** — HTMX 3초 폴링으로 에이전트 상태 실시간 추적
- **타임라인** — Alpine.js 간트차트, 드래그&드롭 + 일/주 전환
- **세션 로그** — 작업 세션 기록 + 옵시디언 다이어리 자동 연동
- **작업 로그** — 일별 작업 기록 + GitHub 스타일 커밋 히트맵 (13주)
- **인프라 비용** — 프로바이더별 비용 추적 + 도넛 차트
- **AI 할일** — GPT-4o 기반 다음 할일 추천 (한국어, 1인 로컬 맥락 반영)
- **인프라 관리** — DB 관리, SQL 실행, 배포 이력, RDS 모니터링, SSH 터미널
- **GitHub 연동** — 커밋 자동 수집 + 이슈 → 할일 동기화
- **인증** — 세션 쿠키 기반 단일 관리자 인증 + Rate Limit

## 빠른 시작

```bash
# 1. 환경 변수 설정
cp .env.example .env
# .env에 DB_PASSWORD, ORBIT_GITHUB_TOKEN, ORBIT_OPENAI_API_KEY 설정

# 2. SSH 터널 (AWS RDS 사용 시)
ssh -i /path/to/key.pem -L 5432:rds-endpoint:5432 ubuntu@bastion-ip -N &

# 3. Docker Compose로 실행
docker compose up -d

# 4. 브라우저에서 확인
# http://localhost:8000 (admin / orbit2026)
```

## 스프린트 이력

| Sprint | 모듈 | 상태 |
|--------|------|------|
| S0 | 프로젝트 뼈대 + ob_projects | done |
| S1 | 에이전트 모니터 (HTMX 3초 폴링) | done |
| S2 | 타임라인/간트차트 (Alpine.js 드래그&드롭) | done |
| S3 | 세션 로그 + 옵시디언 다이어리 연동 | done |
| S4 | 작업 로그 + 커밋 히트맵 | done |
| S5 | 인프라 비용 트래커 | done |
| S6 | AI 할일 추천 (GPT-4o + fallback) | done |
| S7 | 인프라 관리 (DB/배포/RDS/서버) | done |
| Auth | 세션 쿠키 인증 (단일 관리자) | done |
| S8 | 대시보드 트렌드 차트 + AI 프롬프트 개선 | done |
| S9 | UI 보강 + 프로젝트 상태 요약 | done |

## 프로젝트 구조

```
orbit/
├── app/
│   ├── api/            # FastAPI 라우터 (10개, 43 엔드포인트)
│   ├── models/         # SQLAlchemy 모델 (12 테이블)
│   ├── pages/          # Jinja2 페이지 라우터
│   ├── schemas/        # Pydantic 스키마
│   ├── services/       # 비즈니스 로직 (12 서비스)
│   ├── templates/      # Jinja2 HTML (13 템플릿)
│   ├── auth.py         # 세션 쿠키 인증
│   ├── config.py       # 환경변수 설정
│   ├── database.py     # AsyncSession 엔진
│   └── main.py         # FastAPI 앱 + 미들웨어
├── alembic/            # DB 마이그레이션 (9 revisions)
├── tests/              # pytest (9 테스트 파일)
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── seed.py             # 초기 데이터
```

## DB 테이블

```
ob_projects        ob_agents          ob_agent_runs
ob_milestones      ob_sessions        ob_work_logs
ob_commit_stats    ob_infra_costs     ob_todos
ob_deployments     ob_db_migrations   ob_sql_history
ob_server_snapshots
```
