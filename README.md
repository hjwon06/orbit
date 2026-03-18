# ORBIT — 1인 개발자 프로젝트 관제 허브

멀티 프로젝트를 운영하는 솔로 개발자를 위한 통합 관제 대시보드.

## 스택

- **Backend**: Python 3.12 + FastAPI + SQLAlchemy (async)
- **Frontend**: Jinja2 + HTMX + Tailwind CSS
- **Database**: PostgreSQL 16 + pgvector
- **Deploy**: Docker Compose → Coolify + Vultr Seoul VPS

## 빠른 시작

```bash
# 1. 환경 변수 설정
cp .env.example .env

# 2. Docker Compose로 실행
docker compose up -d

# 3. 시드 데이터 (선택)
docker compose exec app python seed.py

# 4. 브라우저에서 확인
open http://localhost:8000
```

## 모듈 로드맵

| Sprint | 모듈 | 상태 |
|--------|------|------|
| S0 | 프로젝트 뼈대 + ob_projects | ✅ |
| S1 | 대시보드 + M1 에이전트 모니터 | 🔜 |
| S2 | M2 타임라인/간트차트 | 📋 |
| S3 | M3 세션 로그 뷰어 | 📋 |
| S4 | M4 작업 로그 + M6 커밋 통계 | 📋 |
| S5 | M5 인프라 비용 트래커 | 📋 |
| S6 | M7 AI 할일 추천 | 📋 |

## 프로젝트 구조

```
orbit/
├── app/
│   ├── api/            # FastAPI 라우터 (JSON API)
│   ├── models/         # SQLAlchemy 모델
│   ├── pages/          # Jinja2 페이지 라우터
│   ├── schemas/        # Pydantic 스키마
│   ├── services/       # 비즈니스 로직
│   ├── static/         # CSS, JS
│   ├── templates/      # Jinja2 HTML 템플릿
│   ├── config.py       # 설정
│   ├── database.py     # DB 엔진
│   └── main.py         # FastAPI 앱
├── alembic/            # DB 마이그레이션
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── seed.py
```
