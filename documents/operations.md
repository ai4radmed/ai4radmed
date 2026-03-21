# Operations Guide (운영 및 배포 절차)

> 이 문서는 서버 환경 설정, 오프라인 배포, 자동 구동 등 **운영 절차**를 다룹니다.
> 코딩 규칙과 컨벤션은 `ai-agent-guidelines.md`를 참조하십시오.

---

## 1. Windows WSL2 Optimization (Critical)

> **Disk Space Reclamation**: WSL2의 가상 디스크(`ext4.vhdx`)는 기본적으로 용량이 늘어나기만 하고 줄어들지 않습니다.

- **Requirement**: 윈도우 사용자 홈 디렉터리(`%UserProfile%`)에 `.wslconfig` 파일을 생성하고 아래 내용을 추가해야 합니다.
  ```ini
  [wsl2]
  sparseVhd=true
  ```
- **Effect**: 리눅스에서 파일을 삭제하면 윈도우의 호스트 디스크 용량도 자동으로 회복됩니다. (Docker 로그 폭주 사고 예방 필수)

---

## 2. Offline Installation Strategy (Closed Network)

> **대상**: 병원 내부망 등 인터넷 접근이 차단된 폐쇄망 환경.
> **전제**: 외부에서 미리 빌드된 Docker Image(.tar)와 소스 코드를 USB 등의 물리 매체로 반입합니다.

### A. Image Delivery (USB Strategy)
1.  **Export (Internet PC)**:
    - 외부망 PC에서 필요한 이미지를 `docker save` 명령으로 파일화합니다.
    - 예: `docker save -o dcmtk_3.6.7.tar ai4radmed-dcmtk:3.6.7`
    - **중요**: 모든 이미지는 `latest`가 아닌 **고정된 버전(Pinned Version)**을 사용해야 합니다. (예: `3.6.7`)

2.  **Import (Hospital Server)**:
    - USB를 서버에 마운트하고 이미지를 로드합니다.
    - 예: `docker load -i /path/to/usb/dcmtk_3.6.7.tar`

### B. Configuration Adjustment
- `docker-compose.yml`에서 `build:` 섹션을 주석 처리하고 `image:` 섹션만 활성화합니다.
- 로컬 빌드 대신 로드된 이미지를 사용하도록 `ai4radmed-cli.py`나 `Makefile`을 조정합니다.

---

## 3. Auto-Start Strategy (OS별 자동 구동 전략)

> **목표**: 서버 부팅(또는 로그인) 시 Docker 컨테이너와 필수 서비스(Vault Unseal 등)를 사람의 개입 없이 자동으로 구동 완료 상태로 만듭니다.

### A. Linux & Windows 11 (WSL2 w/ Systemd)

**전제 조건**: `systemd`가 활성화되어 있어야 합니다. (`ps --no-headers -o comm 1` → `systemd`)

1.  **Docker Container**: `restart: unless-stopped` 정책에 의해 Docker 서비스 구동 시 자동 복구됨. (별도 설정 불필요)
2.  **Auto-Unseal Service**:
    - **Service File**: `/etc/systemd/system/ai4radmed-unseal.service` 등록.
    - **Trigger**: `After=docker.service` (도커 구동 직후 실행).
    - **Action**: `ai4radmed-cli.py unseal-vault` 명령 실행 (Mock USB 등 키 파일 감지).

### B. Windows 10 (Docker Desktop / Native)

1.  **Docker Desktop 사용자 (일반적)**:
    - **설정**: Settings > General > **Start Docker Desktop when you log in** 체크.
    - **WSL Integration**: Settings > Resources > WSL Integration > 사용 중인 배포판(Ubuntu 등) **ON**.
    - **결과**: 윈도우 로그인 시 컨테이너 자동 구동. (단, Unseal은 3번 스크립트로 처리)

2.  **Native Docker 사용자 (WSL2 Custom)**:
    - **sudoers**: `/etc/sudoers`에 `NOPASSWD: /usr/sbin/service docker start` 추가.
    - **Start Script**: 윈도우 `shell:startup` 폴더에 `start_docker.bat` 배치 파일 생성.
    - **내용**: `wsl -d Ubuntu -u root service docker start`

3.  **Auto-Unseal (Windows 공통)**:
    - `shell:startup` 폴더에 `auto_unseal.bat` 생성.
    - 내용:
      ```batch
      @echo off
      wsl -d Ubuntu -u ben /home/ben/projects/ai4radmed/.venv/bin/python /home/ben/projects/ai4radmed/scripts/ai4radmed/auto_unseal.py
      ```

### C. Restore Strategy
- **절차**: `stop` -> `template check` -> `restore(overwrite)` -> `permission fix` -> `start`
