# ORBIT DB 스키마 현황

> 추출일: 2026-03-18
> DB: AWS RDS PostgreSQL 16 (jay_db)
> 방법론: 애자일 (스프린트 단위 마이그레이션, Alembic 9 revisions)

---

## 요약

| 항목 | 수치 |
|------|------|
| 테이블 수 | 13개 (+ alembic_version) |
| 총 행 수 | 74 rows |
| FK 관계 | 10개 |
| 인덱스 | 1개 (ob_projects.slug) |
| Soft Delete 적용 | 5개 테이블 (deleted_at) |

---

## 테이블별 상세

### ob_projects (중심 테이블) — 3 rows

| 컬럼 | 타입 | NULL | 비고 |
|------|------|------|------|
| id | integer PK | NOT NULL | auto increment |
| name | varchar(100) | NOT NULL | |
| slug | varchar(50) | NOT NULL | UNIQUE INDEX |
| description | text | NULL | |
| status | varchar(20) | NULL | active / paused / archived |
| repo_url | varchar(500) | NULL | GitHub 연동용 |
| stack | varchar(200) | NULL | |
| color | varchar(7) | NULL | 대시보드 카드 색상 |
| created_at | timestamptz | NULL | DEFAULT now() |
| updated_at | timestamptz | NULL | DEFAULT now() |
| deleted_at | timestamptz | NULL | Soft Delete |

- IDX: `ix_ob_projects_slug` (UNIQUE)

---

### ob_agents — 11 rows

| 컬럼 | 타입 | NULL | 비고 |
|------|------|------|------|
| id | integer PK | NOT NULL | auto increment |
| project_id | integer FK | NOT NULL | → ob_projects.id |
| agent_code | varchar(10) | NOT NULL | A0, A1, A2... |
| agent_name | varchar(100) | NOT NULL | |
| model_tier | varchar(20) | NULL | opus / sonnet |
| status | varchar(20) | NULL | idle / running / error |
| current_task | varchar(200) | NULL | |
| last_heartbeat | timestamptz | NULL | |
| created_at | timestamptz | NULL | DEFAULT now() |
| deleted_at | timestamptz | NULL | Soft Delete |

- FK: `project_id` → `ob_projects.id`

---

### ob_agent_runs — 8 rows

| 컬럼 | 타입 | NULL | 비고 |
|------|------|------|------|
| id | integer PK | NOT NULL | auto increment |
| agent_id | integer FK | NOT NULL | → ob_agents.id |
| task_name | varchar(200) | NOT NULL | |
| status | varchar(20) | NULL | running / success / error / cancelled |
| error_log | text | NULL | |
| duration_sec | integer | NULL | |
| started_at | timestamptz | NULL | DEFAULT now() |
| finished_at | timestamptz | NULL | |

- FK: `agent_id` → `ob_agents.id`

---

### ob_milestones — 14 rows

| 컬럼 | 타입 | NULL | 비고 |
|------|------|------|------|
| id | integer PK | NOT NULL | auto increment |
| project_id | integer FK | NOT NULL | → ob_projects.id |
| title | varchar(200) | NOT NULL | |
| status | varchar(20) | NULL | planned / active / done |
| start_date | date | NOT NULL | |
| end_date | date | NOT NULL | |
| color | varchar(7) | NULL | 간트차트 색상 |
| sort_order | integer | NULL | |
| github_issue_url | varchar(500) | NULL | GitHub 연동 선반영 |
| github_issue_number | integer | NULL | GitHub 연동 선반영 |
| source | varchar(20) | NULL | manual / github |
| created_at | timestamptz | NULL | DEFAULT now() |
| updated_at | timestamptz | NULL | DEFAULT now() |
| deleted_at | timestamptz | NULL | Soft Delete |

- FK: `project_id` → `ob_projects.id`

---

### ob_sessions — 0 rows

| 컬럼 | 타입 | NULL | 비고 |
|------|------|------|------|
| id | integer PK | NOT NULL | auto increment |
| project_id | integer FK | NOT NULL | → ob_projects.id |
| title | varchar(200) | NOT NULL | |
| agent_code | varchar(10) | NULL | |
| summary | text | NULL | Markdown |
| status | varchar(20) | NULL | running / done |
| started_at | timestamptz | NULL | DEFAULT now() |
| finished_at | timestamptz | NULL | |
| duration_min | integer | NULL | |
| created_at | timestamptz | NULL | DEFAULT now() |
| deleted_at | timestamptz | NULL | Soft Delete |

- FK: `project_id` → `ob_projects.id`

---

### ob_work_logs — 0 rows

| 컬럼 | 타입 | NULL | 비고 |
|------|------|------|------|
| id | integer PK | NOT NULL | auto increment |
| project_id | integer FK | NOT NULL | → ob_projects.id |
| log_date | date | NOT NULL | upsert 키 (project_id + date) |
| content | text | NULL | Markdown |
| created_at | timestamptz | NULL | DEFAULT now() |
| updated_at | timestamptz | NULL | DEFAULT now() |

- FK: `project_id` → `ob_projects.id`

---

### ob_commit_stats — 1 row

| 컬럼 | 타입 | NULL | 비고 |
|------|------|------|------|
| id | integer PK | NOT NULL | auto increment |
| project_id | integer FK | NOT NULL | → ob_projects.id |
| stat_date | date | NOT NULL | upsert 키 (project_id + date) |
| commit_count | integer | NULL | |
| additions | integer | NULL | |
| deletions | integer | NULL | |
| source | varchar(20) | NULL | manual / github |
| created_at | timestamptz | NULL | DEFAULT now() |

- FK: `project_id` → `ob_projects.id`

---

### ob_infra_costs — 2 rows

| 컬럼 | 타입 | NULL | 비고 |
|------|------|------|------|
| id | integer PK | NOT NULL | auto increment |
| project_id | integer FK | NOT NULL | → ob_projects.id |
| provider | varchar(50) | NOT NULL | Vultr, AWS, Cloudflare... |
| service_name | varchar(100) | NOT NULL | |
| cost_usd | double precision | NULL | |
| billing_cycle | varchar(20) | NULL | monthly / yearly / one-time |
| is_active | boolean | NULL | |
| notes | text | NULL | |
| created_at | timestamptz | NULL | DEFAULT now() |
| updated_at | timestamptz | NULL | DEFAULT now() |

- FK: `project_id` → `ob_projects.id`

---

### ob_todos — 30 rows

| 컬럼 | 타입 | NULL | 비고 |
|------|------|------|------|
| id | integer PK | NOT NULL | auto increment |
| project_id | integer FK | NOT NULL | → ob_projects.id |
| title | varchar(300) | NOT NULL | |
| description | text | NULL | |
| priority | varchar(10) | NULL | high / medium / low |
| status | varchar(20) | NULL | open / done |
| source | varchar(20) | NULL | manual / ai / github |
| github_issue_url | varchar(500) | NULL | GitHub 이슈 연동 |
| ai_reasoning | text | NULL | GPT 추천 이유 |
| created_at | timestamptz | NULL | DEFAULT now() |
| completed_at | timestamptz | NULL | |
| deleted_at | timestamptz | NULL | Soft Delete |

- FK: `project_id` → `ob_projects.id`

---

### ob_deployments — 0 rows

| 컬럼 | 타입 | NULL | 비고 |
|------|------|------|------|
| id | integer PK | NOT NULL | auto increment |
| project_id | integer FK | NOT NULL | → ob_projects.id |
| target | varchar(50) | NOT NULL | |
| commit_sha | varchar(40) | NULL | |
| branch | varchar(100) | NULL | |
| status | varchar(20) | NULL | running / success / failed |
| log | text | NULL | 배포 로그 |
| duration_sec | integer | NULL | |
| triggered_by | varchar(50) | NULL | |
| started_at | timestamptz | NULL | DEFAULT now() |
| finished_at | timestamptz | NULL | |

- FK: `project_id` → `ob_projects.id`

---

### ob_db_migrations — 0 rows

| 컬럼 | 타입 | NULL | 비고 |
|------|------|------|------|
| id | integer PK | NOT NULL | auto increment |
| project_id | integer FK | NOT NULL | → ob_projects.id |
| db_alias | varchar(50) | NOT NULL | |
| migration_name | varchar(200) | NOT NULL | |
| direction | varchar(10) | NULL | up / down |
| status | varchar(20) | NULL | |
| log | text | NULL | |
| executed_at | timestamptz | NULL | DEFAULT now() |

- FK: `project_id` → `ob_projects.id`

---

### ob_sql_history — 4 rows

| 컬럼 | 타입 | NULL | 비고 |
|------|------|------|------|
| id | integer PK | NOT NULL | auto increment |
| db_alias | varchar(50) | NOT NULL | |
| query | text | NOT NULL | |
| row_count | integer | NULL | |
| duration_ms | integer | NULL | |
| status | varchar(20) | NULL | success / error |
| error | text | NULL | |
| executed_at | timestamptz | NULL | DEFAULT now() |

- FK 없음 (독립 테이블)

---

### ob_server_snapshots — 0 rows

| 컬럼 | 타입 | NULL | 비고 |
|------|------|------|------|
| id | integer PK | NOT NULL | auto increment |
| server_name | varchar(50) | NOT NULL | |
| cpu_pct | numeric | NULL | |
| memory_pct | numeric | NULL | |
| disk_pct | numeric | NULL | |
| memory_used_mb | integer | NULL | |
| memory_total_mb | integer | NULL | |
| disk_used_gb | numeric | NULL | |
| disk_total_gb | numeric | NULL | |
| load_avg_1m | numeric | NULL | |
| process_count | integer | NULL | |
| uptime_hours | integer | NULL | |
| raw_data | json | NULL | CloudWatch 원본 |
| collected_at | timestamptz | NULL | DEFAULT now() |

- FK 없음 (독립 테이블)

---

## 관계도 (ER)

```
ob_projects (1)
  ├──(1:N)── ob_agents ──(1:N)── ob_agent_runs
  ├──(1:N)── ob_milestones
  ├──(1:N)── ob_sessions
  ├──(1:N)── ob_work_logs
  ├──(1:N)── ob_commit_stats
  ├──(1:N)── ob_infra_costs
  ├──(1:N)── ob_todos
  ├──(1:N)── ob_deployments
  └──(1:N)── ob_db_migrations

ob_sql_history        (독립)
ob_server_snapshots   (독립)
```

---

## 데이터 현황

| 테이블 | 행 수 | 비고 |
|--------|-------|------|
| ob_projects | 3 | Giniz, DAESIN, ORBIT |
| ob_agents | 11 | 3개 프로젝트 에이전트 |
| ob_agent_runs | 8 | 에이전트 실행 이력 |
| ob_milestones | 14 | S0~S9 + Auth + 기타 |
| ob_sessions | 0 | cc() 연동 제거로 미사용 |
| ob_work_logs | 0 | 수동 입력 대기 |
| ob_commit_stats | 1 | GitHub 동기화 1일분 |
| ob_infra_costs | 2 | 활성 서비스 2개 |
| ob_todos | 30 | AI 추천 + 수동 |
| ob_deployments | 0 | 시뮬레이션만 |
| ob_db_migrations | 0 | 미사용 |
| ob_sql_history | 4 | SQL 실행 이력 |
| ob_server_snapshots | 0 | 수집 라우트 미구현 |

---

## Alembic 마이그레이션 이력

| Revision | 스프린트 | 내용 |
|----------|---------|------|
| 001 | S0 | ob_projects 생성 |
| 002 | S1 | ob_agents + ob_agent_runs 생성 |
| 003 | S2 | ob_milestones 생성 |
| 004 | S3 | ob_sessions 생성 |
| 005 | S4 | ob_work_logs + ob_commit_stats 생성 |
| 006 | S5 | ob_infra_costs 생성 |
| 007 | S6 | ob_todos 생성 |
| 008 | S7 | ob_deployments + ob_db_migrations + ob_sql_history + ob_server_snapshots 생성 |
| 009 | — | Soft Delete (deleted_at) + 개선 |
