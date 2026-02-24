# PostgreSQL Service Guide

> **서비스명**: `ai4radmed-postgres`
> **역할**: 모든 서비스의 공통 관계형 데이터베이스
> **Image**: `postgres:16.3-alpine` (Pinned Version)
> **Network**: `ai4radmed-data` (내부 전용, 호스트 포트 바인딩 없음)

## 1. Architecture

### 1.1 Service Layout
- **Container Name**: `ai4radmed-postgres`
- **Internal Port**: `5432` (호스트 노출 없음 - [SEC-08] Network Segmentation)
- **Data Volume**: `/opt/ai4radmed/postgres/data`
- **Security**:
  - `read_only: true` ([SEC-09] Immutable Infrastructure)
  - `tmpfs`: `/var/run/postgresql`, `/tmp` (쓰기 필요 영역만 허용)

### 1.2 Managed Databases
초기화 스크립트(`templates/postgres/init/`)가 다음 DB를 자동 생성합니다:
- `ai4radmed`: 기본 DB
- `keycloak`: Keycloak 인증 서버용 (`01-init-keycloak.sh`)
- `orthanc_mock`, `orthanc_raw`, `orthanc_pseudo`: PACS 서비스용 (`02-init-orthanc.sh`)

## 2. Configuration

### 2.1 Config Files
- **`config/postgres.yml`**: 메모리 제한, 백업 스케줄.
- **`.env`**: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`.
- **`templates/postgres/config/`**: `postgresql.conf`, `pg_hba.conf`, `pg_ident.conf`.

### 2.2 Backup Policy
```yaml
backup:
  schedule: "0 3 * * *"  # 매일 03:00 (Hot Backup)
  retention_days: 30
```

## 3. 2-Step TLS Initialization (핵심 전략)

> **문제**: PostgreSQL은 데이터 디렉터리(`/var/lib/postgresql/data`) 및 `postgres` 사용자가 생성되기 **전에는** 인증서에 올바른 권한(`chown postgres:postgres`)을 부여할 수 없습니다.

### Step 1: 평문 구동 (Bootstrap)
- `docker-compose.override.yml`(TLS 설정)을 **제외**하고 기본 템플릿만 복사하여 구동.
- DB 초기화 및 볼륨 생성이 수행됨.

### Step 2: TLS 적용 (Hardening)
- 인증서 발급 및 권한 설정 (`chown postgres:postgres`).
- `docker-compose.override.yml` 추가 복사.
- 재기동하여 TLS 모드 적용.

### TLS Override 설정
`docker-compose.override.yml`은 다음을 활성화합니다:
- `ssl=on`, `ssl_cert_file`, `ssl_key_file`, `ssl_ca_file` (mTLS)
- `pg_hba.conf` 마운트 (클라이언트 인증서 검증)

### DB 초기화 검증 (필수)
설치 완료 시 반드시 `psql -l` 명령을 통해 생성된 DB 목록을 로그로 출력하여 초기화 스크립트 실행 여부를 검증해야 합니다.

## 4. Troubleshooting

- **인증서 권한 오류**: `chown` 실패 시 Step 1부터 재실행. `--reset` 옵션으로 볼륨 삭제 후 재시작.
- **Init Script 미실행**: 이미 초기화된 볼륨이 존재하면 `docker-entrypoint-initdb.d` 스크립트가 실행되지 않음. `--reset` 필요.
- **Connection Refused**: `ai4radmed-data` 네트워크에 접속하는 서비스만 통신 가능. 호스트 포트 바인딩 없음에 주의.
