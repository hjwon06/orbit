# ORBIT — 프로젝트 전용 지식

> 팀 프로젝트 관제 허브 (멀티유저 RBAC)
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
| Auth | 세션 쿠키 인증 (→ RBAC에서 멀티유저로 전환) | done |
| S8 | 대시보드 트렌드 차트 (Chart.js 28일) + AI 할일 프롬프트 개선 | done |
| S9 | UI 보강 (에러페이지, 스키마 필드, 프로젝트 수정/삭제, 스파크라인, 비용 도넛차트) | done |
| S10 | 에이전트 오케스트레이터 + UI 다듬기 (사이드바, 아이콘, 필터, 활동시간, 드롭다운) | done |
| S11 | Glass 디자인 + AI 고도화 (주간 요약, 우선순위 재정렬, 진행률 바) | done |
| S12 | 고도화 (GraphQL 전환, soft delete 정리, 다이어리 동기화, 마일스톤 진행률) | done |
| S13 | 서버 비용 대시보드 (AWS CE + Vultr API 실시간 조회) | done |
| S14 | 레포 품질 평가 (clone→ruff/mypy/bandit/radon→GPT 리뷰) + 웹 터미널 | done |
| S15 | 브랜치별 커밋 현황 (Compare API + PR 커밋 조회 + 60초 폴링) | done |
| RBAC | 멀티유저 인증 (ob_users, bcrypt, admin/member 역할 분기) | done |
| — | AI 할일 기능 삭제 (S6, S8 관련 코드/UI 전면 제거) | done |

---

## DB 테이블

```
ob_projects     ← S0 (중심 테이블, 모든 모듈의 FK 대상)
ob_agents       ← S1
ob_agent_runs   ← S1 (에이전트 오케스트레이터 연동)
ob_milestones   ← S2 (github_issue_url, github_issue_number, source 필드 선반영)
ob_sessions     ← S3 (세션 시작/종료 + 마크다운 요약 + 옵시디언 자동 저장)
ob_work_logs    ← S4 (날짜별 작업 기록, upsert 방식)
ob_commit_stats ← S4 (날짜별 커밋 통계, GitHub 자동 수집)
ob_infra_costs  ← S5 (프로바이더별 서비스 비용, monthly/yearly/one-time)
ob_todos        ← S6 (코드 제거됨, DB 테이블만 잔존)
ob_sql_history  ← S7 (SQL 쿼리 실행 이력)
ob_repo_scores  ← S14 (레포 품질 평가 결과, project_id unique)
ob_users        ← RBAC (username unique, password_hash bcrypt, role admin/member)

삭제됨 (S10): ob_deployments, ob_db_migrations, ob_server_snapshots
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

### 9. Windows Python Hook stdin 인코딩 깨짐
**증상**: Claude Code Hook 스크립트(`orbit_agent_start.py`)에서 한글 포함된 description 처리 시 `UnicodeEncodeError: surrogates not allowed`.
**원인**: Windows `sys.stdin`이 기본 cp949로 디코딩 → UTF-8 한글이 서로게이트 문자(`\udcec`)로 깨짐.
**해결**: `json.load(sys.stdin)` → `json.loads(sys.stdin.buffer.read().decode("utf-8"))` (start/finish 양쪽).
**적용 범위**: Windows에서 Claude Code Hook으로 Python 스크립트를 실행할 때 한글 입력이 있으면 항상 `sys.stdin.buffer` 사용 필수.

### 10. alembic env.py 삭제된 모델 import 잔존
**증상**: `alembic upgrade head` 시 `ImportError: cannot import name 'Deployment'`.
**원인**: S10에서 `ob_deployments`, `ob_db_migrations`, `ob_server_snapshots` 테이블과 모델을 삭제했으나, `alembic/env.py`의 import 목록에서 제거하지 않음.
**해결**: env.py에서 `Deployment`, `DbMigration`, `ServerSnapshot` import 제거.
**교훈**: 모델/테이블 삭제 시 alembic/env.py import도 반드시 정리할 것.

### 11. Hook JSON null 파싱 에러
**증상**: Hook에서 세션 생성 API 호출 시 `"There was an error parsing the body"`.
**원인**: `agent_code: None`을 JSON으로 보내면 `null`이 되는데, Pydantic `Optional[str]`이 JSON body에서 `null`을 정상 처리하지만 `urlopen`의 Request 방식에서 파싱 문제 발생.
**해결**: `agent_code` 필드를 body에서 아예 제거 (Optional이므로 서버에서 기본값 적용).
**교훈**: Hook에서 ORBIT API 호출 시 None/null 필드는 body에서 생략하는 것이 안전.

### 12. RDS 전환 후 seed 미실행 → 빈 DB
**증상**: jay 계정 로그인은 되지만 프로젝트/에이전트가 하나도 안 보임.
**원인**: RDS로 전환 후 `python seed.py`를 실행하지 않아 ob_projects, ob_agents, ob_milestones 테이블이 비어있었음.
**교훈**: DB 전환/마이그레이션 후 seed 실행 체크리스트 필수. project_yaml도 seed에 포함해야 MCP 배지 표시됨.

### 13. rate limit 로컬 IP 미면제 → 로그인 잠김
**증상**: 비밀번호 리셋 후에도 브라우저에서 "아이디 또는 비밀번호가 잘못되었습니다" 반복.
**원인**: 브라우저 IP가 172.x/192.168.x 대역이면 rate limit 면제 안 됨. 5회 실패 후 15분 잠김. 서버 메모리 기반이라 재시작해야 풀림.
**해결**: exempt IP에 172.x, 192.168.x 추가. 디버그 로깅 추가.
**교훈**: rate limit 면제 IP 범위를 충분히 넓게 잡을 것. 로컬 개발 환경에서 다양한 IP가 올 수 있음.

### 14. DAESIN_AGENTS 하드코딩 잔재
**증상**: 에이전트 seed 버튼 누르면 삭제된 DAESIN 프로젝트의 영문 에이전트가 생성됨.
**원인**: `pages/__init__.py`에 `DAESIN_AGENTS` 리스트가 하드코딩되어 있었음.
**해결**: project_yaml 기반 동적 로딩 + local_path 기반 자동 동기화로 교체.

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
| 미사용 테이블 제거 | ob_deployments, ob_db_migrations, ob_server_snapshots DROP | 데이터 0건 + 코드 미사용, 필요 시 재생성 |
| 에이전트 오케스트레이터 | AuthMiddleware 로컬 면제 + lookup API | Claude Code → ORBIT 에이전트 모니터 자동 연동 |
| Hook stdin 인코딩 | sys.stdin.buffer + UTF-8 decode | Windows cp949 기본값 회피, 한글 서로게이트 방지 |
| 사이드바 비활성화 | Jinja2 조건부 렌더링 (alert → cursor-not-allowed) | 프로젝트 미선택 시 메뉴 비활성화 |
| 모듈 카드 아이콘 | SVG 아이콘 6개 (사이드바와 동일) | 스캔가능성 향상 |
| 비용 필터 | showActiveOnly 토글 + filteredCosts | 활성/전체 전환 |
| 마지막 활동 시간 | MAX(session.started_at, commit.created_at) | 대시보드 카드에 상대 시간 표시 |
| 세션 드롭다운 | agents_json → select 프리셋 | 자유입력 대신 에이전트 목록 선택 |
| GitHub 마일스톤 동기화 | 불필요 → ORBIT 중심 관리 | 1인 개발자에게 GitHub 마일스톤은 이중 관리, ORBIT이 source of truth |
| 마일스톤 진행률 | 할일(todo) 완료율 기반 자동 계산 | milestone_id FK로 연결, 수동 status 변경 대신 할일 체크로 진행률 추적 |
| GitHub 자동동기화 | 페이지 로드 시 auto_sync (10분 쿨다운) | project_detail + logs_page에서 트리거, 메모리 캐시로 중복 방지 |
| Hook 세션 자동생성 | 첫 에이전트 실행 시 세션 생성 (2시간 쿨다운) | tmp 파일에 session_id 저장, 기존 세션 자동 종료 |
| Hook git remote 감지 | CWD에서 git remote get-url origin 자동 감지 | repo_url 비어있으면 자동 PATCH |
| GitHub GraphQL 전환 | REST N+1 → GraphQL 단일 쿼리 | 30커밋 기준 31회→1회, REST fallback 보존 |
| soft delete 일관성 | 전 서비스 deleted_at.is_(None) + hard→soft delete | 42개 쿼리 필터 + 4개 delete 함수 전환 |
| 세션 실시간 타이머 | Alpine.js liveTimer() HH:MM:SS | 1초 갱신, _tick reactive, running 세션만 |
| 다이어리 동기화 | 옵시디언 → 할일 자동 생성/완료 | "내일 할 일"→생성, "오늘 한 일"→GPT 매칭 완료, 1시간 쿨다운 |
| AI 마일스톤 배정 | GPT 프롬프트에 ms ID 포함 + valid_ms_ids 검증 | fallback에서도 m.id 자동 배정 |
| 주간 마일스톤 | W{주차} 자동 생성 + 만료 done + 미완료 이월 | source="weekly", 월요일 기준 |
| 다이어리→할일 동기화 | 옵시디언 파싱 → Todo 생성/완료 | diary_ref unique, GPT-4o 매칭, 1시간 쿨다운 |
| project.yaml DB 저장 | Hook에서 PATCH API로 자동 저장 | ob_projects.project_yaml 컬럼 (Alembic 013) |
| 서버 총비용 대시보드 | AWS CE boto3 + Vultr API v2 httpx | 10분 메모리 캐시, 키 미설정 시 graceful skip, /server-costs |
| 브랜치 커밋 현황 | Compare API + PR commits API | 고유 커밋만 표시, 머지된 브랜치는 PR 커밋 복원, 5분 캐시 + 60초 폴링 |
| RBAC | ob_users + bcrypt + 쿠키에 role 포함 | admin 3명(미아/양양/제이) + member 5명, 미들웨어에서 페이지/API 분기 |
| RDS 포트 변경 | 5432→15432 SSH 터널 | toctoc-postgres가 5432 점유, docker-compose.yml host.docker.internal:15432 |
| Docker git credential | 컨테이너 시작 시 자동 설정 | git config credential.helper store + ORBIT_GITHUB_TOKEN → private repo 클론 |
| AI 할일 삭제 | Todo 모델/서비스/API/UI 전면 제거 | 사용 안 하는 기능 정리, -445줄, ob_todos 테이블은 DB에 잔존 |

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
| ~~AI 할일~~ | ~~ClickUp, Todoist~~ | 삭제됨 (S15) |
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
| 5 | 권한 | ✅ 멀티유저 RBAC (admin: 인프라/서버비용/레포품질, member: 제한) |
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
ssh -f -N -L 15432:giniz-db.cbyc4yk4c3iq.ap-northeast-2.rds.amazonaws.com:5432 \
    -i /c/Users/win11/Desktop/AWSKEY/giniz-key.pem ubuntu@15.164.25.18
docker compose up -d

# → http://localhost:8000
# 관리자: jay/jay1234, mia/mia1234, yangyang/yang1234
# 일반: sunny/sunny1234, jimmy/jimmy1234, chloe/chloe1234, joy/joy1234, jaesoon/jaesoon1234
```
