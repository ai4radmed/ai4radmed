# AI Agent Guidelines
> 이 문서는 AI Code Assistant (Gemini, Claude 등)가 코드를 생성할 때 **항상** 준수해야 할 핵심 규칙입니다.
> 서비스별 세부사항은 아래 Section 4의 링크를 참조하십시오.

## 0. Language Policy (언어 정책)
> **최우선 지침**: 본 프로젝트의 모든 커뮤니케이션은 **한국어(Korean)**를 원칙으로 합니다.

1.  **Scope**: 채팅 대화, 상태 요약, 기술 문서 및 주석 모두 한국어.
2.  **Terminology**: 전문 용어는 최초 1회 **한글(English)** 형태로 병기. 유머/은유 배제, **명확하고 전문적인 어조** 유지.

## 0.1 Core Philosophy (코드 철학)
> **기본 철학**: "서툰 사용자(Non-Expert User)"와 "디테일이 약한 관리자(Maintainer)"를 위한 프로젝트.
> 아래 4가지 원칙은 **우선순위 순서**입니다. 원칙 간 충돌 시 번호가 낮은 것이 우선합니다.

1.  **가독성 최우선 (Readability First)**:
    -   **"읽히는 바보 같은 코드"** > "돌아가기만 하는 복잡한 코드".
    -   6개월 뒤 유지보수 담당자가 즉시 이해하고 수정할 수 있어야 합니다.
    -   간결성은 가독성을 해치지 않는 범위 내에서만 추구합니다. 비슷한 3줄 코드가 섣부른 추상화보다 낫습니다.

2.  **적극적 로깅 (Verbose Meaningful Logging)**:
    -   **함수 단위가 아닌, 비즈니스 단위(의미 있는 실행 단위)**로 로깅합니다.
    -   좋은 예: "Vault unseal 시작" → "USB 감지 완료" → "키 복호화 성공" → "Unseal 완료"
    -   나쁜 예: ~~"함수 A 호출됨" → "함수 B 호출됨"~~ (의미 없음)
    -   **에러 로그에는 반드시 "어디서(Where), 왜(Why), 어떻게 해결(How)"**을 포함합니다.
    -   이를 통해 전화 너머의 사용자가 에러 메시지만 읽어줘도 원인 파악이 가능해야 합니다.

3.  **조용히 실패하지 않는다 (Fail Loudly)**:
    -   예외를 삼키지(`except: pass`) 않습니다. 실패 시 원인과 해결 방법을 로그로 명시합니다.
    -   "알 수 없는 오류"는 금지. 모든 예외 메시지에 **맥락(Context)**을 포함합니다.
    -   예: `log_error(f"[Vault Unseal] 실패: {e}. USB 마운트 확인: ls /mnt/usb/vault_keys.enc")`

4.  **테스트로 증명한다 (Test as Proof)**:
    -   구현 후 반드시 테스트를 작성합니다. 테스트가 없는 기능은 미완성입니다.
    -   **Unit Test**: 순수 로직 (파싱, 변환 등) → 항상 실행 가능.
    -   **Integration Test**: 컨테이너 연동 → 서비스 구동 후 실행.
    -   **Smoke Test**: 설치 직후 최소 동작 확인 → `make install-*` 후 자동 실행.
    -   GS 인증 제출용 리포트 자동 생성 (상세: [Testing Strategy](#8-testing--certification-strategy-테스트-전략)).

### 0.2 Security (보안 — 도메인 요구사항)
> 보안은 코드 철학이 아닌 **의료 인프라의 필수 요구사항**으로, 별도 관리합니다.

-   검증된 오픈소스로 **12 Pillars of World Class Security** 구현:
    Immutable Infrastructure, WAF, Network Segmentation, DDoS/Rate Limiting, Zero Trust Gateway, Centralized Identity (OIDC), MFA, RBAC, Secret Management (Vault), Split Knowledge, E2E Encryption, Audit Logging
-   상세 구현 계획: [Security Implementation Plan](documents/security-implementation-plan.md) 참조.

## 1. Project Context (프로젝트 개요)
- **이름**: `ai4radmed` — RPython 연구회의 공통 인프라(보안, 데이터베이스 등) 구축/관리 플랫폼.
- **핵심 목표**: 오픈소스를 활용한 안정적인 인프라 서비스 제공.

## 2. Tech Stack & Environment (기술 스택)
- **OS**: Linux (주) / Windows / macOS. 코드 제안 시 OS 간 경로(`\` vs `/`)와 권한 분기 고려.
- **Languages**: Python 3.x (`.python-version` 참조), R (`renv`).
- **Virtual Environment**: Python `.venv` (표준 `venv`), R `renv`.
- **Configuration**: `.env` 파일에서 환경변수(`PROJECT_NAME`, `LOG_LEVEL` 등) 로드.
- **WSL2/배포 환경 설정**: [Operations Guide](documents/operations.md) 참조.

## 3. Coding Standards (코딩 컨벤션)
> 코드의 "왜"는 Section 0.1 철학을 따르고, 여기서는 **"어떻게"** 만 기술합니다.

### 3.1 Python Import Path
- **기준 경로**: `{PROJECT_ROOT}/src` (`sys.path`에 추가됨)
- **예시**: `src/common/logger.py` → `from common.logger import log_info`

### 3.2 Logging (도구 및 설정)
**`print()` 사용 금지.** 반드시 전용 로거 사용:
- **Python**: `from common.logger import log_info, log_error` (설정: `config/logging.yml`)
- **R**: `src/R/logger.R` (`log_debug`, `log_info`, `log_warn`, `log_error`, `log_critical`)
- **Level**: 개발 `LOG_LEVEL=DEBUG`, 운영 `INFO` 이상.
- **Format**: `common.logger` 표준 포맷 절대 준수 (ELK/HIPAA Audit 연동).

### 3.3 Container Naming Convention
- **Prefix**: 모든 컨테이너 이름은 반드시 **`ai4radmed-`** 접두사.
- **Format**: `ai4radmed-{service_name}` (예: `ai4radmed-vault`, `ai4radmed-postgres`)
- **CLI**: `scripts/ai4radmed/ai4radmed-cli.py`

## 4. Project Structure (프로젝트 구조)

프로젝트의 세부 아키텍처는 `documents/` 폴더 내 각 문서를 참조하십시오.

> **규칙**: 실제 존재하는 문서만 기재. 서비스 추가 시 문서를 생성한 뒤 이 목록에 추가할 것.

**1. Core Infrastructure (필수/기반)**
- [PostgreSQL Service Guide](documents/postgres.md): 공통 관계형 데이터베이스 및 2-Step TLS.
- [Vault Service Guide](documents/vault.md): 보안 키/시크릿 관리, Smart Key, Auto-Unseal.
- [Security Implementation Plan](documents/security-implementation-plan.md): 12 Pillars 구현 계획 및 검증 체크리스트.
- [Operations Guide](documents/operations.md): WSL2 설정, 오프라인 배포, 자동 구동 전략.

**2. Application Services (선택)**
- [Vaultwarden Service Guide](documents/vaultwarden.md): 패스워드 매니저.

**3. Identity Management (선택 - SSO/계정)**
- [OpenLDAP Guide](documents/ldap.md): 중앙 계정 저장소.
- [Keycloak Guide](documents/keycloak.md): 통합 인증 및 SSO.

**4. Gateway & Access Control (선택 - 접근 제어)**
- [OIDC Gateway Guide](documents/oidc-gateway.md): OpenResty 기반 Zero Trust 게이트웨이.

**5. Observability (선택 - 로그/모니터링)**
- [ELK Stack Guide](documents/elk.md): 로그 수집 및 시각화.

**6. Medical & AI Data Ops (선택 - 의료/AI 특화)**
- [Orthanc Guide](documents/orthanc.md): 의료 영상(DICOM) PACS 서버.
- [Slicer Guide](documents/slicer.md): 3D Slicer 이미지 분석.
- [OpenREM Guide](documents/openrem.md): 방사선량 관리 플랫폼.

**주요 디렉터리:**
- `templates/`: 서비스별 Docker Compose 템플릿. 서비스 생성 시 복사하여 사용.
- `scripts/`: 설치, 셋업, 백업 등 자동화 스크립트.
- `src/`: 주요 소스 코드 (Python/R).
- `config/`: 서비스 설정 파일 (`*.yml`).
- `docs/`: Quarto 렌더링 결과물. **변경 불가(템플릿 표준)**.

## 5. Configuration Policy (설정 원칙)
> **철학**: "사용자가 설정을 통해 시스템을 배우게 하되, 위험한 자유는 제한한다."

1.  **설정 노출**: 포트, 메모리 등 안전한 값은 `config/<service>.yml`로 노출. 하드코딩 지양.
2.  **경로 고정**: 데이터 마운트 경로는 코드 레벨에서 고정 (사용자 설정 불가).
3.  **변수 전략**:
    - `.env`: 전역 변수 및 민감 정보 (비밀번호 등).
    - `config/*.yml`: `service.enable`, `env_vars` (컨테이너 환경변수), `compose_vars` (Docker Compose 치환변수).
    - Docker Compose: `${VAR:-Default}` 형식, 이미지 버전 태그 명시.
    - **작동 원리**: 전용 스크립트가 설정을 병합하여 서비스 전용 `.env`를 동적 생성.
4.  **네트워크 바인딩**: 컨테이너 내부 Listen Address는 반드시 **`0.0.0.0`** (Loopback 금지).

## 6. Automation & Workflow (자동화)
- `make setup`: 초기 환경 설정. `make venv`: 가상환경 생성.
- 새 기능은 가급적 Makefile 타겟이나 `scripts/` 내 파이썬 스크립트로 모듈화.
- 오프라인 설치, 자동 구동 전략: [Operations Guide](documents/operations.md) 참조.

### Reset Strategy (Clean Install)
> `--reset` 사용 시, 반드시 **컨테이너 자체를 삭제**(`docker rm -f`)해야 합니다.
> Stateful Container(LDAP, DB 등)는 Bootstrap 시에만 설정을 생성하므로, 재활용 시 오류 발생.
> **절차**: `docker rm -f <container>` -> `rm -rf <volume_dir>` -> `start (Re-create)`

## 7. Security Principles (보안 원칙)

### TLS Implementation Strategy (적용 기준)
1.  **Native TLS (One-Shot)** (예: Vault): 설정 파일로 인증서 경로 지정, 최초 구동 시 즉시 TLS.
2.  **2-Step Initialization** (예: Postgres): 평문 구동 → 사용자/폴더 생성 → 인증서 권한 → TLS 재기동.
3.  **Reverse Proxy Termination** (예: Web Apps): Nginx가 TLS 처리, 내부 평문. (단, Vault 등 보안 서비스는 내부도 TLS)

### Recovery Policy (복구 정책)
- **General**: `make restore-<service>` → 최신 백업 자동 복원.
- **Point-in-Time**: CLI 직접 사용 → `ai4radmed-cli.py restore <service> <backup_file_path>`

## 8. Testing & Certification Strategy (테스트 전략)
> **목표**: GS 인증 획득 대비, 기능 구현과 테스트를 분리된 프로세스로 관리.

### Dual-Track Verification
- **Track A (Automated)**: `tests/security/`, `pytest` + `requests`. 실행: `make test-security`.
- **Track B (Manual)**: `security-implementation-plan.md` 내 "Manual Guide" 섹션. "Action → Expectation" 형식.

### Test Standards
- **Framework**: `pytest`. Unit Test + Integration Test.
- **Documentation**: 모든 테스트 함수에 "평가 항목"과 "기대 결과" Docstring 포함.

### Reporting
- 비전문가도 이해 가능한 문서 형태 리포트 (GS 인증 제출용).
- 경로: `documents/test-reports/{version}/report_{date}.md`

## 9. Application Delivery Strategy (앱 배포 전략)
> **원칙**: "사용자는 **컨테이너**로 실행, 개발자는 **로컬 가상환경**에서 개발."

1.  **Runtime**: Docker Only. 호스트에 직접 설치 금지. 웹 접근: `http://service.ai4radmed.internal`.
2.  **Development**: 각 앱 리포지토리(`apps/`)마다 개별 `.venv`.
3.  **Delivery**: Docker Image (`.tar` 또는 Registry) + `config/*.yml` (Git).
