# ORBIT — 프로젝트 전용 지식

> 1인 개발자 프로젝트 관제 허브
> 스택: FastAPI + Jinja2 + HTMX + Alpine.js + Tailwind + PostgreSQL 16 + pgvector

---

## 현재 상태

| Sprint | 모듈 | 상태 |
|--------|------|------|
| S0 | 프로젝트 뼈대 + ob_projects | done |
| S1 | 에이전트 모니터 (HTMX 3초 폴링) | done |
| S2 | 타임라인/간트차트 (Alpine.js 드래그&드롭) | done |
| S3 | 세션 로그 뷰어 + 옵시디언 다이어리 연동 | done |
| S4 | 작업 로그 + 커밋 통계 (히트맵) | done |
| S5 | 인프라 비용 트래커 | done |
| S6 | AI 할일 추천 (GPT-4o + fallback) | done |
| S7 | 인프라 관리 (DB/배포/RDS/서버 모니터링) | done |
| Auth | 세션 쿠키 인증 (단일 관리자) | done |
| S8 | 대시보드 트렌드 차트 (Chart.js 28일) + AI 할일 프롬프트 개선 | done |
| S9 | UI 보강 (에러페이지, 스키마 필드, 프로젝트 수정/삭제, 스파크라인, 비용 도넛차트) | done |

---

## DB 테이블

```
ob_projects     ← S0
ob_agents       ← S1
ob_agent_runs   ← S1
ob_milestones   ← S2 (github_issue_url, github_issue_number, source 필드 S6용 선반영)
ob_sessions     ← S3 (세션 시작/종료 + 마크다운 요약 + 옵시디언 자동 저장)
ob_work_logs    ← S4 (날짜별 작업 기록, upsert 방식)
ob_commit_stats ← S4 (날짜별 커밋 통계, 수동 입력 → S6에서 GitHub 자동 수집)
ob_infra_costs  ← S5 (프로바이더별 서비스 비용, monthly/yearly/one-time)
ob_todos        ← S6 (수동 + AI 추천 + GitHub 이슈 연동 준비)
ob_deployments  ← S7 (배포 이력, 백그라운드 실행)
ob_db_migrations ← S7 (마이그레이션 실행 이력)
ob_sql_history  ← S7 (SQL 쿼리 실행 이력, 위험 쿼리 차단)
ob_server_snapshots ← S7 (서버 CPU/메모리/디스크 스냅샷)
```

---

## 실패 패턴 / 함정

### 1. seed.py 다중 루프 문제
**증상**: `docker compose exec app python seed.py` 실행 시 첫 번째 루프(프로젝트)만 동작하고 이후 루프(에이전트, 마일스톤) 출력이 안 나옴.
**원인**: 미확인. async session + commit 후 후속 루프 실행은 되지만 출력이 누락되는 것으로 추정.
**우회**: 시드 데이터를 별도 인라인 스크립트(`python -c "..."`)로 직접 실행.
**TODO**: seed.py 루프 구조 디버깅 필요.

### 2. alembic 컨테이너 내부 실행 불가
**증상**: `docker compose exec app alembic upgrade head` → `[Errno 111] Connect call failed ('127.0.0.1', 5432)`
**원인**: `alembic.ini`의 `sqlalchemy.url`이 `localhost`를 가리킴. 컨테이너 내부에서는 DB 호스트가 `db`여야 함.
**우회**: `seed.py`의 `Base.metadata.create_all()`로 테이블 직접 생성.
**해결안**: alembic.ini에서 환경변수 참조하도록 수정 (`%(ORBIT_DATABASE_URL_SYNC)s`) 또는 env.py에서 docker-compose 환경변수 우선 사용.

### 3. seed.py 볼륨 마운트 필요
**증상**: seed.py 수정 후 `docker compose exec app python seed.py` 해도 이전 코드 실행됨.
**원인**: Dockerfile `COPY . .`로 빌드 시점의 seed.py가 복사됨. `./app`만 마운트되어 seed.py는 반영 안 됨.
**해결**: `docker-compose.yml`에 `./seed.py:/app/seed.py` 볼륨 추가. (S3에서 적용됨)

### 5. alembic stamp 필요 (create_all로 만든 DB)
**증상**: `alembic upgrade head` 시 "relation already exists" 에러.
**원인**: `Base.metadata.create_all()`로 테이블을 만들어서 alembic_version 테이블에 기록이 없음.
**해결**: `alembic stamp 007_sprint6`으로 현재 revision 동기화 후 정상 동작.

### 6. Git Bash psql → RDS SSL 인증 실패
**증상**: `PGPASSWORD='Jay!2026' psql -h 127.0.0.1 -U jay -d jay_db` → `password authentication failed`
**원인**: Git Bash의 psql이 SSH 터널 + RDS SSL 조합에서 인증 협상을 제대로 못 함.
**확인**: Python `psycopg2`로는 동일 비번으로 정상 접속됨 (`sslmode=require`).
**결론**: psql 접속 실패해도 앱(asyncpg)에는 영향 없음. DB 확인은 DBeaver 또는 Python 스크립트 사용.

### 7. alembic env.py sslmode→ssl 변환 필요
**증상**: `alembic stamp` 시 `connect() got an unexpected keyword argument 'sslmode'`
**원인**: env.py에서 sync URL(`sslmode=require`)을 asyncpg URL로 변환할 때 asyncpg는 `ssl=require`만 인식.
**해결**: `.replace("sslmode=", "ssl=")` 추가.

### 8. Alpine.js + defer 로딩 순서
**패턴**: `base.html`에서 `<script defer>` 로 Alpine.js 로드 → 템플릿의 `{% block scripts %}`에서 `alpine:init` 이벤트 리스너로 컴포넌트 등록 → 정상 동작.
**주의**: Alpine.js보다 먼저 `x-data`에서 사용할 전역 변수(`window.__milestones` 등)를 선언해야 함.

---

## 기술 결정 기록

| 결정 | 선택 | 이유 |
|------|------|------|
| 간트차트 라이브러리 | Alpine.js 직접 구현 | HTMX 스택 유지, ORBIT 디자인 톤 일관성, JSX/React 금지 |
| 에이전트 모니터 갱신 | HTMX hx-trigger="every 3s" | 서버 사이드 렌더링 유지, WebSocket 불필요 |
| 타임라인 뷰 | 일/주 전환 | 제이님 요구사항, colWidth 40px(일)/120px(주) |
| GitHub 연동 준비 | 테이블 필드 선반영 | S6에서 활용, 현재는 nullable |
| DB 방법론 | 애자일 | 워터폴 금지, 스프린트 단위 마이그레이션 |
| 마크다운 에디터 | textarea + marked.js 미리보기 | 외부 에디터 라이브러리 없이, 편집/미리보기 토글 |
| 옵시디언 연동 | 컨테이너 볼륨 마운트 (/obsidian) | 세션 종료 시 서버에서 직접 파일 쓰기, 같은 날 이어쓰기 |
| 커밋 히트맵 | CSS grid + Alpine.js (13주) | GitHub 스타일 잔디, 외부 라이브러리 없이 |
| 작업 로그/커밋 통계 | upsert 방식 (같은 날짜 덮어쓰기) | 하루 1건 원칙, unique index (project_id, date) |
| 인프라 비용 | 프로바이더별 서비스 등록, 활성/비활성 | monthly cost 자동 합산, yearly는 /12 변환 |
| AI 할일 추천 | GPT-4o + fallback (키 없으면 마일스톤 기반) | try/except 필수, httpx 비동기 호출 |
| 대시보드 집계 | SQLAlchemy func 직접 쿼리 | 크로스 프로젝트 요약 6개 위젯 |
| GitHub 연동 | httpx + GitHub REST API v3 | 토큰+repo_url 미설정 시 graceful skip, 설정 즉시 동작 |
| 인증 | itsdangerous 서명 쿠키 (7일) | AuthMiddleware, 페이지→리다이렉트, API→401, /login /logout 공개 |
| 테스트 | pytest + httpx → 실행 중 서버에 직접 요청 | asyncpg 풀 문제 우회, conftest에서 uuid slug 사용 |
| DB 전환 | Docker PostgreSQL → AWS RDS (SSH 터널) | jay_db, SSL 필수, `.bashrc` cc() 자동화 |
| SSL 설정 | asyncpg: `ssl=require` / psycopg2: `sslmode=require` | 드라이버마다 파라미터명 다름 |
| 에이전트 모니터 연동 | cc() 함수에서 start_run/finish_run 자동 호출 | CWD로 프로젝트 판별, claude 종료 시 자동 idle |
| 모바일 반응형 | Alpine.js sidebarOpen + 오버레이 | md 이상은 기존 사이드바, 미만은 햄버거 슬라이드 |
| 대시보드 카드 통계 | GROUP BY project_id 한 번에 집계 | N+1 쿼리 방지, 에이전트/마일스톤/세션/커밋 4개 |
| 대시보드 트렌드 | Chart.js CDN + 라인 차트 | 28일 세션+커밋 추이, 고정 높이 div 필수 (무한 확장 방지) |
| AI 할일 프롬프트 | 완료 마일스톤 제외 + 한국어 강제 | done 마일스톤 표시, 중복 추천 방지, 진행 중 마일스톤 중심 |
| cc() 단순화 | SSH 터널 + Claude만 | ORBIT 세션 자동 기록 제거 (서버 상시 가동 불가) |
| 404/500 에러 페이지 | error.html + FastAPI exception_handler | API→JSON, 페이지→ORBIT 디자인 에러 화면 |
| 프로젝트 수정/삭제 | project_detail.html Alpine.js 모달 | PATCH/DELETE API 연동, confirm 삭제 |
| 스파크라인 | Chart.js 미니 라인 (카드 내 36px) | 프로젝트별 7일 세션+커밋 합산, animation:false |
| 비용 도넛차트 | Chart.js doughnut (cutout 60%) | 프로바이더별 비율, $watch로 실시간 갱신 |
| 스키마 보강 | TodoUpdate +ai_reasoning/source, AgentUpdate +agent_name | API로 수정 가능 필드 확대 |

---

## 디자인 토큰

```
배경: #FAFAF7 (warm off-white)
카드: #FFFFFF
보더: #E8E6E1
뮤트: #8C8A84
액센트: #534AB7 (purple)
성공: #0F6E56
위험: #A32D2D
폰트: Pretendard Variable
```

---

## Grounding — Reference Architecture

> ORBIT 각 모듈의 설계 원본. 새 기능 추가 시 여기서 참조.

| 모듈 | Reference | 참조 포인트 |
|------|-----------|-----------|
| 프로젝트 관리 | Jira, Linear | 프로젝트/이슈 구조, 상태 머신 |
| 에이전트 모니터 | Datadog, Prometheus | 에이전트 상태, heartbeat, run 이력 |
| 타임라인/간트 | MS Project, Asana | 마일스톤, 의존관계, 간트 뷰 |
| 세션 로그 | Splunk, ELK | 세션 시작/종료, 로그 수집 |
| 작업 로그/커밋 | GitHub, GitLab | 커밋 통계, 일별 활동, 히트맵 |
| 인프라 비용 | AWS Cost Explorer | 프로바이더별 비용, billing cycle |
| AI 할일 | ClickUp, Todoist | 우선순위, AI 추천, 상태 관리 |
| 인프라 관리 | Terraform, Ansible | DB 관리, 배포, 서버 모니터링 |
| 대시보드 | Grafana | 크로스 프로젝트 집계, 위젯 |

## Canonical — 네이밍 표준

```
테이블: ob_ 접두사 + snake_case (ob_projects, ob_agents...)
컬럼: snake_case (created_at, updated_at, project_id...)
상태값: lowercase (active, idle, running, error, done, planned)
API: /api/{리소스} REST (GET 목록, POST 생성, PATCH 수정, DELETE 삭제)
URL: /projects/{slug}/{모듈} (에이전트, 타임라인, 세션 등)
```

## 12개 체크리스트 (ORBIT 적용)

| # | 항목 | ORBIT 현재 |
|---|------|-----------|
| 1 | 서버에서 실행 | ✅ FastAPI 서버 처리 |
| 2 | DB 저장 | ✅ PostgreSQL RDS |
| 3 | FK/관계 | ✅ project_id FK 전체 적용 |
| 4 | 삭제 정책 | ✅ Soft Delete (deleted_at, 5개 주요 테이블) |
| 5 | 권한 | ✅ 단일 관리자 세션 쿠키 |
| 6 | 조회 규칙 | ✅ 프로젝트별 필터 + deleted_at IS NULL |
| 7 | 트랜잭션 | ✅ AsyncSession commit/rollback |
| 8 | 예외 케이스 | ✅ GPT fallback, graceful skip |
| 9 | 시간 기준 | ✅ UTC 저장 + KST 표시 (Jinja2 \|kst 필터) |
| 10 | 계산 순서 | ✅ 비용 monthly+yearly/12 |
| 11 | 규칙 위치 | ✅ 서비스 레이어 분리 |
| 12 | 시도 제한 | ✅ Rate Limit (5회/15분, IP+계정) |

---

## 로컬 실행

```bash
# 1. SSH 터널 + Claude Code (cc 명령어가 자동 처리)
cc

# 2. 또는 수동
ssh -i /c/Users/win11/Desktop/AWSKEY/giniz-key.pem -o StrictHostKeyChecking=no \
    -L 5432:giniz-db.cbyc4yk4c3iq.ap-northeast-2.rds.amazonaws.com:5432 \
    ubuntu@15.164.25.18 -N &
docker compose up -d

# → http://localhost:8000 (admin / orbit2026)
```
