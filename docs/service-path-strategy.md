# SERVICE_PATH 운영체제별 설정 전략 분석

## Windows 서비스 경로 권장사항

### 🏆 1순위: `C:\ProgramData\{PROJECT_NAME}` (권장)
**특징:**
- Windows 시스템 서비스 표준 위치
- 관리자 권한으로 설치되는 전역 서비스에 적합
- 모든 사용자가 접근 가능 (권한 설정에 따라)
- Docker Desktop과 호환성 우수
- Windows 서비스 규약 준수

**예시 구조:**
```
C:\ProgramData\ai4radmed\
├── postgres\
│   ├── data\
│   ├── config\
│   └── backup\
├── vault\
│   ├── data\
│   ├── config\
│   └── certs\
└── logs\
```

### 🥈 2순위: `%USERPROFILE%\{PROJECT_NAME}` (사용자별)
**특징:**
- 사용자별 설치에 적합
- 권한 문제 최소화
- 개발/테스트 환경에 적합
- Docker Desktop의 기본 볼륨 마운트와 호환

**예시 구조:**
```
C:\Users\{username}\ai4radmed\
├── services\
├── data\
└── logs\
```

### 🥉 3순위: `C:\{PROJECT_NAME}` (루트 직접)
**특징:**
- 가장 간단하고 직관적
- 경로가 짧아 Docker 볼륨 마운트 시 유리
- 권한 설정 주의 필요

## 플랫폼별 SERVICE_PATH 비교

| 플랫폼 | 경로 | 권한 | 특징 |
|--------|------|------|------|
| **Linux** | `/opt/{PROJECT_NAME}` | sudo 필요 | 시스템 전역, 표준 |
| **macOS** | `/usr/local/{PROJECT_NAME}` | sudo 필요 | Homebrew 스타일 |
| **Windows** | `C:\ProgramData\{PROJECT_NAME}` | 관리자 권한 | 시스템 서비스 표준 |
| **Windows (사용자)** | `%USERPROFILE%\{PROJECT_NAME}` | 사용자 권한 | 개발환경 적합 |

## 실제 활용 방법

### 1. 환경변수 기반 자동 경로 설정
```python
import os
import platform
from pathlib import Path

def get_service_path(project_name="ai4radmed"):
    system = platform.system().lower()
    
    if system == "linux":
        return Path(f"/opt/{project_name}")
    elif system == "darwin":  # macOS
        return Path(f"/usr/local/{project_name}")
    elif system == "windows":
        # ProgramData 우선, 권한 없으면 사용자 폴더
        try:
            programdata = Path(f"C:/ProgramData/{project_name}")
            if programdata.parent.exists():
                return programdata
        except:
            pass
        return Path.home() / project_name
    else:
        return Path.home() / project_name
```

### 2. Docker Compose 템플릿에서 활용
```yaml
# templates/postgres/docker-compose.yml
services:
  postgres:
    volumes:
      - ${SERVICE_PATH}/postgres/data:/var/lib/postgresql/data
      - ${SERVICE_PATH}/postgres/backup:/backup
    
# Linux: /opt/ai4radmed/postgres/data
# Windows: C:\ProgramData\ai4radmed\postgres\data
```

### 3. 설정 파일에서 참조
```yaml
# config/services/postgres.yml
postgres:
  install_dir: "${SERVICE_PATH}/postgres"
  data_dir: "${SERVICE_PATH}/postgres/data"
  backup_dir: "${SERVICE_PATH}/postgres/backup"
  config_dir: "${SERVICE_PATH}/postgres/config"
```

## 권한 관리 전략

### Linux/macOS
```bash
# 디렉터리 생성 시 sudo 필요
sudo mkdir -p /opt/ai4infra
sudo chown $USER:$USER /opt/ai4infra
```

### Windows (ProgramData)
```powershell
# 관리자 권한으로 실행
New-Item -Path "C:\ProgramData\ai4infra" -ItemType Directory -Force
# ACL 설정으로 권한 조정
```

### Windows (사용자별)
```powershell
# 사용자 권한으로 실행 가능
New-Item -Path "$env:USERPROFILE\ai4infra" -ItemType Directory -Force
```

## AI4RM CLI에서의 활용

### 플랫폼 감지 및 자동 설정
```python
# ai4rm-cli platform setup
def setup_platform():
    service_path = get_service_path()
    
    # .env 파일 업데이트
    update_env_file("SERVICE_PATH", str(service_path))
    
    # 디렉터리 생성
    create_service_directories(service_path)
    
    # 권한 설정
    setup_permissions(service_path)
```

### 서비스별 경로 관리
```python
class ServicePathManager:
    def __init__(self, project_name="ai4infra"):
        self.base_path = Path(os.getenv("SERVICE_PATH") or get_service_path(project_name))
    
    def get_service_path(self, service):
        return self.base_path / service
    
    def get_data_path(self, service):
        return self.get_service_path(service) / "data"
    
    def get_config_path(self, service):
        return self.get_service_path(service) / "config"
```

## 마이그레이션 시나리오

### 기존 사용자 (Linux/WSL2 → Windows)
```bash
# 1. 기존 데이터 백업
ai4rm-cli backup all --output=/backup/migration

# 2. Windows 환경 설정
ai4rm-cli platform setup --target=windows

# 3. 데이터 복원
ai4rm-cli restore all --from=/backup/migration
```

## 권장사항

1. **기본값**: `C:\ProgramData\{PROJECT_NAME}` 사용
2. **개발환경**: 사용자별 경로 옵션 제공
3. **Docker 호환**: 짧은 경로명 고려
4. **권한 관리**: 플랫폼별 적절한 권한 설정 자동화
5. **마이그레이션**: 플랫폼 간 데이터 이동 도구 제공

이 전략을 통해 크로스플랫폼 환경에서 일관된 서비스 관리가 가능해집니다.
