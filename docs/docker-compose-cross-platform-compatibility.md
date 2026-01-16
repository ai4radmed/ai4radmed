# Docker Compose WSL2 ↔ Windows Docker Desktop 호환성 분석

## 현재 프로젝트의 호환성 문제점

### ❌ 문제가 되는 볼륨 마운트들

#### 1. **절대 경로 하드코딩 (PostgreSQL)**
```yaml
volumes:
  - ${PG_DATA_DIR:-/opt/ai4radmed/postgresql/data}:/var/lib/postgresql/data
```
**문제**: `/opt/ai4radmed/` 경로가 Windows에 존재하지 않음

#### 2. **Linux 시스템 디렉터리 마운트 (Vault, ELK)**
```yaml
volumes:
  - /etc/localtime:/etc/localtime:ro          # ❌ Windows에 없음
  - /usr/share/zoneinfo:/usr/share/zoneinfo:ro # ❌ Windows에 없음
  - /var/log:/var/log:ro                      # ❌ Windows에 없음
```

#### 3. **상대 경로의 다른 해석**
```yaml
volumes:
  - ./docker/elk/esdata:/usr/share/elasticsearch/data
```
**문제**: 현재 작업 디렉터리 기준이 다를 수 있음

## 해결방안

### 방안 1: **조건부 Compose 파일** (권장)

#### A. 플랫폼별 Compose 파일 분리
```bash
# 디렉터리 구조
templates/postgres/
├── docker-compose.yml           # 공통 설정
├── docker-compose.linux.yml     # Linux/WSL2 전용
├── docker-compose.windows.yml   # Windows 전용
└── docker-compose.override.yml  # 로컬 오버라이드
```

#### B. Linux/WSL2용 (docker-compose.linux.yml)
```yaml
services:
  postgres:
    volumes:
      - ${PG_DATA_DIR:-/opt/ai4radmed/postgresql/data}:/var/lib/postgresql/data
      - /etc/localtime:/etc/localtime:ro
      - /usr/share/zoneinfo:/usr/share/zoneinfo:ro

  vault:
    volumes:
      - ./file:/vault/file
      - ./config:/vault/config
      - ./certs:/vault/certs
      - /etc/localtime:/etc/localtime:ro
      - /usr/share/zoneinfo:/usr/share/zoneinfo:ro
```

#### C. Windows용 (docker-compose.windows.yml)
```yaml
services:
  postgres:
    volumes:
      - ${PG_DATA_DIR:-C:/ProgramData/ai4radmed/postgresql/data}:/var/lib/postgresql/data
      # Windows는 시간대를 환경변수로 처리
    environment:
      - TZ=Asia/Seoul

  vault:
    volumes:
      - ./file:/vault/file
      - ./config:/vault/config
      - ./certs:/vault/certs
    environment:
      - TZ=Asia/Seoul
```

#### D. 실행 스크립트 자동화
```python
# scripts/docker_manager.py
import platform
import subprocess
import os

class DockerComposeManager:
    def __init__(self):
        self.platform = self._detect_platform()
    
    def _detect_platform(self):
        system = platform.system().lower()
        if system == "linux":
            if os.path.exists("/proc/version"):
                with open("/proc/version", "r") as f:
                    if "microsoft" in f.read().lower():
                        return "wsl2"
            return "linux"
        elif system == "windows":
            return "windows"
        return "unknown"
    
    def get_compose_files(self, service):
        """플랫폼에 맞는 compose 파일 목록 반환"""
        base_file = f"templates/{service}/docker-compose.yml"
        platform_file = f"templates/{service}/docker-compose.{self.platform}.yml"
        
        files = ["-f", base_file]
        if os.path.exists(platform_file):
            files.extend(["-f", platform_file])
        
        return files
    
    def run_compose(self, service, action="up -d"):
        """플랫폼에 맞게 docker compose 실행"""
        compose_files = self.get_compose_files(service)
        cmd = ["docker", "compose"] + compose_files + action.split()
        
        print(f"실행 명령: {' '.join(cmd)}")
        return subprocess.run(cmd, cwd=f"templates/{service}")

# 사용 예시
manager = DockerComposeManager()
manager.run_compose("postgres", "up -d")
```

### 방안 2: **환경변수 기반 조건부 설정**

#### A. 확장된 .env 파일
```bash
# .env
PROJECT_NAME=ai4infra
PLATFORM=linux  # linux, wsl2, windows 자동 감지

# Linux/WSL2 설정
PG_DATA_DIR_LINUX=/opt/ai4infra/postgresql/data
VAULT_DATA_DIR_LINUX=/opt/ai4infra/vault

# Windows 설정  
PG_DATA_DIR_WINDOWS=C:/ProgramData/ai4infra/postgresql/data
VAULT_DATA_DIR_WINDOWS=C:/ProgramData/ai4infra/vault

# 플랫폼별 시간대 처리
USE_HOST_TIMEZONE=true  # Linux: volume mount, Windows: env var
```

#### B. 스마트 Compose 파일
```yaml
services:
  postgres:
    image: postgres:16.3-alpine
    volumes:
      # 플랫폼별 조건부 데이터 디렉터리
      - ${PG_DATA_DIR:-${PG_DATA_DIR_LINUX:-/opt/ai4infra/postgresql/data}}:/var/lib/postgresql/data
    environment:
      - TZ=${TZ:-Asia/Seoul}
      
  vault:
    image: hashicorp/vault:latest
    volumes:
      - ${VAULT_CONFIG_DIR:-./config}:/vault/config
      - ${VAULT_DATA_DIR:-./file}:/vault/file
      - ${VAULT_CERTS_DIR:-./certs}:/vault/certs
    environment:
      - TZ=${TZ:-Asia/Seoul}

# 조건부 오버라이드 (docker-compose.override.yml에서 처리)
```

### 방안 3: **Docker Desktop의 WSL2 통합 활용**

Docker Desktop for Windows는 WSL2 백엔드를 사용할 수 있어서:

```yaml
# 단일 compose 파일로 처리 가능
services:
  postgres:
    volumes:
      # WSL2 경로를 Windows에서도 인식 가능
      - /mnt/c/ProgramData/ai4infra/postgresql/data:/var/lib/postgresql/data
      
  vault:
    volumes:
      - ./config:/vault/config
      - ./file:/vault/file
      - ./certs:/vault/certs
    environment:
      - TZ=Asia/Seoul  # 환경변수로 시간대 처리
```

## 실제 테스트 결과 예상

### ✅ **즉시 작동할 것들**
- 기본 서비스 시작/중지
- 네트워크 통신
- 포트 포워딩
- 기본 환경변수

### ⚠️ **문제가 발생할 것들**
- `/opt/ai4infra/` 경로 접근 실패
- `/etc/localtime`, `/usr/share/zoneinfo` 마운트 실패  
- `/var/log` 디렉터리 마운트 실패
- 권한 관련 문제 (chown, chmod)

### 💡 **권장 즉시 테스트**
```bash
# 1. 기본 PostgreSQL 테스트 (상대 경로만 사용)
cd templates/postgres
# 환경변수 오버라이드로 Windows 경로 지정
PG_DATA_DIR=C:/temp/postgres-data docker compose up -d

# 2. Vault 테스트 (시간대 볼륨 마운트 제거)
cd templates/vault  
# vault compose 파일에서 /etc/localtime 마운트 주석 처리 후 테스트
docker compose up -d
```

## 결론

**동일한 Docker Compose 파일로는 완전히 호환되지 않지만**, 약간의 수정으로 크로스플랫폼 지원이 가능합니다. 

**권장 접근법**: 
1. **방안 1 (조건부 Compose 파일)**을 구현
2. 플랫폼 자동 감지 스크립트 작성  
3. 점진적으로 모든 서비스에 적용

이렇게 하면 WSL2와 Windows Docker Desktop 모두에서 동일한 명령어로 컨테이너를 구동할 수 있습니다.
