# ORBIT 작업 세션 로그 — 2026-03-17

> 이 문서를 새 세션에서 읽으면 현재 상태를 바로 파악할 수 있습니다.

---

## 완료된 작업 전체

### Sprint 0~7 + 품질/운영

| Sprint | 모듈 | 상태 |
|--------|------|------|
| S0 | 프로젝트 뼈대 + ob_projects | done |
| S1 | 에이전트 모니터 (HTMX 3초 폴링) | done |
| S2 | 타임라인/간트차트 (Alpine.js 드래그&드롭, 일/주 뷰) | done |
| S3 | 세션 로그 + 옵시디언 다이어리 자동 생성 | done |
| S4 | 작업 로그 + 커밋 통계 (GitHub 스타일 히트맵) | done |
| S5 | 인프라 비용 트래커 (프로바이더별 관리) | done |
| S6 | AI 할일 추천 (GPT-4o + fallback) | done |
| S7 | 인프라 관리 (DB/배포/RDS 모니터링/서버 상태) | done |
| QA | ruff + mypy 통과 + pytest 43개 전체 pass | done |
| Auth | 세션 쿠키 인증 (itsdangerous, 로그인/로그아웃) | done |
| Alembic | 컨테이너 내부 실행 수정 (환경변수 우선) | done |
| Dashboard | 크로스 프로젝트 요약 6개 위젯 | done |
| GitHub | 커밋 동기화 + 이슈 동기화 API (토큰 설정 시 즉시 동작) | done |
| Deploy | docker-compose.prod.yml + DEPLOY.md (Coolify + Vultr 가이드) | done |
| Agents | ORBIT 에이전트 6개 등록 (A0~A4 + QA) | done |
| AgentMon | cc() 실행 시 에이전트 모니터 자동 연동 (start/finish) | done |
| Mobile | 모바일 반응형 (햄버거 메뉴 + 슬라이드 사이드바) | done |
| CardStats | 대시보드 프로젝트 카드 미니 통계 4개 | done |
| RDS | AWS RDS 연결 (SSH 터널 + SSL) | done |
| SSH | EC2 SSH 웹 콘솔 (CWD 프리셋 + 자주 쓰는 명령) | done |
| RDS-SQL | RDS psql 웹 콘솔 (giniz_master@postgres, DB 선택) | done |
| Grounding | 글로벌 CLAUDE.md/REFERENCE.md Grounding+Canonical+12체크리스트 | done |
| SoftDel | Soft Delete 5개 테이블 (deleted_at + 조회 필터) | done |
| KST | UTC→KST 표시 (Jinja2 \|kst 필터) | done |
| RateLimit | 로그인 시도 제한 (5회/15분, IP+계정, localhost 면제) | done |
| InfraCost | AWS 인프라 비용 등록 (EC2 $110 + RDS $170 = $280/월) | done |
| SessionAuto | cc() 세션 자동 생성/종료 | done |
| DiaryView | 옵시디언 다이어리 웹 뷰어 (작업 로그 페이지 통합) | done |

---

## DB 현황

### 현재 DB: AWS RDS (SSH 터널 경유) ✅ 2026-03-17 연결 완료
```
호스트 로컬: postgresql://jay:Jay!2026@localhost:5432/jay_db?sslmode=require
컨테이너:   postgresql+asyncpg://jay:Jay!2026@host.docker.internal:5432/jay_db?ssl=require
RDS 엔드포인트: giniz-db.cbyc4yk4c3iq.ap-northeast-2.rds.amazonaws.com
바스천 서버: ubuntu@15.164.25.18
SSH 키: /c/Users/win11/Desktop/AWSKEY/giniz-key.pem
```

### SSH 터널 (필수 — 매 세션마다)
- `.bashrc`에 `cc()` 함수로 자동화됨 (`cc` 입력 시 터널 + Claude Code 실행)
- 수동 실행: `ssh -i /c/Users/win11/Desktop/AWSKEY/giniz-key.pem -o StrictHostKeyChecking=no -L 5432:giniz-db.cbyc4yk4c3iq.ap-northeast-2.rds.amazonaws.com:5432 ubuntu@15.164.25.18 -N &`
- 확인: `netstat -ano | grep ":5432.*LISTENING"`

### 새 세션에서 해야 할 것
1. SSH 터널 확인 (cc 명령어로 자동, 또는 수동)
2. `docker compose up -d`
3. `http://localhost:8000` 접속 (admin / orbit2026)

---

## DB 테이블 14개

```
ob_projects          ← S0 (프로젝트 CRUD)
ob_agents            ← S1 (에이전트 모니터)
ob_agent_runs        ← S1 (에이전트 실행 기록)
ob_milestones        ← S2 (타임라인 간트차트, GitHub 필드 선반영)
ob_sessions          ← S3 (세션 시작/종료 + 옵시디언 자동 저장)
ob_work_logs         ← S4 (날짜별 작업 기록, upsert)
ob_commit_stats      ← S4 (커밋 통계, GitHub 동기화 가능)
ob_infra_costs       ← S5 (프로바이더별 비용)
ob_todos             ← S6 (수동 + AI 추천 + GitHub 이슈)
ob_deployments       ← S7 (배포 이력)
ob_db_migrations     ← S7 (마이그레이션 이력)
ob_sql_history       ← S7 (SQL 실행 이력)
ob_server_snapshots  ← S7 (서버 메트릭 스냅샷)
alembic_version      ← Alembic (현재: 009_soft_delete)
```

---

## 에이전트 구조 (ORBIT)

| 코드 | 이름 | Tier | 역할 |
|------|------|------|------|
| A0 | Infrastructure | opus | Docker, Coolify, Vultr 배포 |
| A1 | Backend API | sonnet | FastAPI, 서비스, DB, Alembic |
| A2 | Frontend UI | sonnet | Jinja2, HTMX, Alpine.js, Tailwind |
| A3 | AI & Integration | opus | OpenAI, GitHub 연동 |
| A4 | Data & Analytics | sonnet | 통계, 비용, 대시보드 데이터 |
| QA | QA Verification | opus | ruff + mypy + pytest + GPT 감리 |

Phase: A0 → A1+A2 병렬 → A3+A4 병렬 → QA

---

## 파일 구조

```
orbit/
├── .env                          ← DB URL 수정 필요 (AWS RDS)
├── .env.example
├── .env.production.example       ← 프로덕션 환경변수 템플릿
├── CONTEXT.md                    ← 프로젝트 전용 지식 (실패 패턴, 기술 결정)
├── DEPLOY.md                     ← Coolify + Vultr 배포 가이드
├── ORBIT-SPEC.md                 ← 원본 스펙 (S0+S1)
├── SESSION-LOG.md                ← 이 파일
├── project.yaml                  ← 프로젝트 설정
├── Dockerfile
├── docker-compose.yml            ← 개발용 (db 컨테이너 제거됨)
├── docker-compose.prod.yml       ← 프로덕션용
├── requirements.txt              ← + itsdangerous
├── pytest.ini
├── seed.py
├── alembic/
│   ├── env.py                    ← 환경변수 우선 사용
│   ├── alembic.ini
│   └── versions/
│       ├── 001_sprint0_create_ob_projects.py
│       ├── 002_sprint1_create_agents.py
│       ├── 003_sprint2_create_milestones.py
│       ├── 004_sprint3_create_sessions.py
│       ├── 005_sprint4_create_work_logs.py
│       ├── 006_sprint5_create_infra_costs.py
│       ├── 007_sprint6_create_todos.py
│       └── 008_sprint7_create_infra_mgmt.py
├── app/
│   ├── main.py                   ← AuthMiddleware 포함
│   ├── auth.py                   ← 세션 쿠키 인증
│   ├── config.py                 ← admin 계정 + managed DB/서버 설정
│   ├── database.py
│   ├── api/
│   │   ├── __init__.py           ← 10개 라우터 등록
│   │   ├── projects.py
│   │   ├── agents.py
│   │   ├── milestones.py
│   │   ├── sessions.py
│   │   ├── work_logs.py
│   │   ├── commit_stats.py
│   │   ├── infra_costs.py
│   │   ├── todos.py
│   │   ├── github.py
│   │   └── infra.py
│   ├── models/__init__.py        ← 13개 모델
│   ├── schemas/
│   │   ├── project.py, agent.py, milestone.py
│   │   ├── session.py, work_log.py, commit_stat.py
│   │   ├── infra_cost.py, todo.py, infra.py
│   │   └── __init__.py
│   ├── services/
│   │   ├── __init__.py           ← 프로젝트 서비스
│   │   ├── agent_service.py
│   │   ├── milestone_service.py
│   │   ├── session_service.py    ← 옵시디언 다이어리 자동 생성
│   │   ├── work_log_service.py
│   │   ├── commit_stat_service.py
│   │   ├── infra_cost_service.py
│   │   ├── todo_service.py       ← AI 추천 (GPT-4o + fallback)
│   │   ├── github_service.py     ← GitHub 커밋/이슈 동기화
│   │   ├── db_admin_service.py   ← SQL 실행, 테이블 조회
│   │   ├── deploy_service.py     ← 배포 트리거 (백그라운드)
│   │   ├── server_monitor_service.py
│   │   └── ssh_service.py       ← EC2 SSH + RDS psql 명령 실행
│   ├── pages/__init__.py         ← 11개 페이지 라우트
│   └── templates/
│       ├── base.html             ← 사이드바 8개 메뉴 + 로그아웃 + 모바일 햄버거
│       ├── login.html
│       ├── dashboard.html        ← 6개 요약 위젯
│       ├── project_detail.html   ← 6개 모듈 링크
│       ├── project_form.html
│       ├── agents.html           ← HTMX 3초 폴링
│       ├── timeline.html         ← Alpine.js 간트 드래그&드롭
│       ├── sessions.html         ← 마크다운 에디터 + 미리보기
│       ├── logs.html             ← 작업/커밋 탭 + 히트맵 + GitHub 동기화
│       ├── costs.html            ← 프로바이더별 비용
│       ├── todos.html            ← AI 추천 + GitHub 이슈 동기화
│       ├── infra.html            ← DB관리/배포/RDS/서버 4탭
│       └── partials/
│           ├── agent_cards.html
│           └── timeline_bars.html
├── tests/
│   ├── conftest.py               ← httpx → 실행 중 서버에 직접 요청
│   ├── test_projects.py          (5 tests)
│   ├── test_agents.py            (4 tests)
│   ├── test_milestones.py        (4 tests)
│   ├── test_sessions.py          (4 tests)
│   ├── test_work_logs.py         (4 tests)
│   ├── test_commit_stats.py      (3 tests)
│   ├── test_infra_costs.py       (4 tests)
│   ├── test_todos.py             (5 tests)
│   └── test_infra.py             (10 tests)
```

---

## 기본 계정

```
아이디: admin
비번: orbit2026
```

---

## 실패 패턴 / 알아야 할 것

1. **seed.py 다중 루프** — 첫 commit 후 후속 루프 출력 누락. 별도 인라인 스크립트로 시딩 필요할 수 있음
2. **alembic stamp 필요** — create_all로 만든 DB는 alembic_version이 없어서 `alembic stamp {revision}` 필수
3. **Alpine.js defer 순서** — base.html에서 defer로 로드, 템플릿 scripts 블록에서 `alpine:init` 리스너로 등록
4. **테스트는 실행 중 서버에 직접 요청** — ASGI transport asyncpg 풀 문제로 httpx → localhost:8000 방식
5. **Docker에서 호스트 DB 접속** — `host.docker.internal` 사용 + `extra_hosts` 설정

---

## 기술 스택

```
Backend:  Python 3.12 + FastAPI + SQLAlchemy (async) + Alembic
Frontend: Jinja2 + HTMX + Alpine.js + Tailwind CSS (CDN)
DB:       PostgreSQL 16 + pgvector
Auth:     itsdangerous 서명 쿠키
Deploy:   Docker Compose → Coolify + Vultr Seoul VPS
AI:       GPT-4o (할일 추천) + marked.js (마크다운 렌더링)
Test:     pytest + pytest-asyncio + httpx
Lint:     ruff + mypy
```

---

## 다음에 할 일

1. **GitHub 토큰 연동** — repo_url + 토큰 설정 → 커밋/이슈 자동 동기화 실동작
2. **OpenAI 키 연동** — AI 할일 추천 실제 GPT-4o 호출 (키 이미 있음)
3. **프로젝트별 메모/노트** — 프로젝트 상세에 마크다운 메모 기능
4. **알림/뱃지** — 에이전트 에러, TODO 기한 초과 시 대시보드 경고
5. **커밋 히트맵 실데이터** — GitHub 연동 후 실제 커밋으로 히트맵 채우기 (1번 선행)
6. **다크 모드** — 야간 작업용 테마 토글
7. **통합 검색** — 전체 프로젝트에서 세션/TODO/작업 로그 검색
8. **AWS Cost Explorer 실시간** — Organizations 권한 해결 후 전환
