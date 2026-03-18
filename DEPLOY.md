# ORBIT 배포 가이드 — Coolify + Vultr Seoul

## 1. Vultr VPS 생성

```
리전: Seoul (ICN)
플랜: Cloud Compute — 2 vCPU / 2GB RAM / 55GB NVMe ($12/mo)
OS: Ubuntu 22.04 LTS
```

## 2. Coolify 설치

```bash
ssh root@your-vultr-ip

# Coolify 원클릭 설치
curl -fsSL https://cdn.coollabs.io/coolify/install.sh | bash
```

설치 후 `http://your-vultr-ip:8000` → Coolify 대시보드에서 초기 설정.

## 3. GitHub 연결

Coolify 대시보드 → Settings → Git Sources → GitHub 연결

## 4. ORBIT 배포

### 방법 A: Coolify Docker Compose

1. Coolify → New Resource → Docker Compose
2. GitHub repo 선택 (또는 직접 입력)
3. Docker Compose file: `docker-compose.prod.yml`
4. Environment Variables에 `.env.production.example` 값 입력
5. Deploy

### 방법 B: 수동 배포

```bash
ssh root@your-vultr-ip

# 코드 클론
git clone https://github.com/your-repo/orbit.git /opt/orbit
cd /opt/orbit

# 환경변수 설정
cp .env.production.example .env
nano .env  # 값 입력

# 실행
docker compose -f docker-compose.prod.yml up -d

# 시드 (최초 1회)
docker compose -f docker-compose.prod.yml exec app python seed.py

# alembic 동기화
docker compose -f docker-compose.prod.yml exec app alembic stamp head
```

## 5. 도메인 + SSL (Coolify 자동)

Coolify → Resource → Settings → Domain에 `orbit.yourdomain.com` 입력
→ Let's Encrypt SSL 자동 발급

## 6. 업데이트 배포

```bash
cd /opt/orbit
git pull
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec app alembic upgrade head
```

Coolify 사용 시: GitHub push → 자동 배포 (webhook 설정 시)

## 7. 백업

```bash
# DB 백업
docker compose -f docker-compose.prod.yml exec db pg_dump -U orbit orbit > backup_$(date +%Y%m%d).sql

# 복원
cat backup_20260317.sql | docker compose -f docker-compose.prod.yml exec -T db psql -U orbit orbit
```

## 주의사항

- `.env`에 강한 비밀번호 사용 (DB + 관리자 + secret_key)
- `ORBIT_DEBUG=false` 확인
- 방화벽: 80, 443만 오픈 (8000은 Coolify 리버스 프록시 뒤)
- Vultr 방화벽 그룹에서 SSH(22)는 본인 IP만 허용
