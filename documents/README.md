# 문서 인덱스 (Documentation Index)

> AI 에이전트 및 개발자가 **주제별로 어떤 문서를 볼지** 빠르게 찾기 위한 인덱스입니다.  
> 공통 규칙과 코드 철학은 **[ai-agent-guidelines.md](ai-agent-guidelines.md)** 를 반드시 참조하세요.

---

## 진입점 (Entry Points)

| 대상 | 파일 | 설명 |
|------|------|------|
| **AI 에이전트 (필수)** | [../AGENTS.md](../AGENTS.md) | AI 에이전트 통합 진입점 (System Map) |
| **공통 지침 (필수)** | [ai-agent-guidelines.md](ai-agent-guidelines.md) | 언어 정책, 코드 철학, 코딩 컨벤션, 보안·테스트·배포 전략 등 **전체 규칙** |
| Claude | [../CLAUDE.md](../CLAUDE.md) | Claude용 진입점 → AGENTS.md 참조 |
| Gemini | [../GEMINI.md](../GEMINI.md) | Gemini용 진입점 → AGENTS.md 참조 |

---

## 주제별 문서 매핑 (Topic → Document)

### 1. Core Infrastructure (필수/기반)

| 주제 | 문서 | 설명 |
|------|------|------|
| PostgreSQL, DB, 2-Step TLS | [postgres.md](postgres.md) | 공통 관계형 DB 및 2-Step TLS |
| Vault, 시크릿, 키 관리 | [vault.md](vault.md) | 보안 키/시크릿, Smart Key, Auto-Unseal |
| 보안 구현·검증 | [security-implementation-plan.md](security-implementation-plan.md) | 12 Pillars 구현 계획 및 검증 체크리스트 |
| WSL2, 배포, 자동 구동 | [operations.md](operations.md) | WSL2 설정, 오프라인 배포, 자동 구동 전략 |

### 2. Application Services (선택)

| 주제 | 문서 | 설명 |
|------|------|------|
| 패스워드 매니저 | [vaultwarden.md](vaultwarden.md) | Vaultwarden 서비스 가이드 |

### 3. Identity Management (SSO/계정)

| 주제 | 문서 | 설명 |
|------|------|------|
| LDAP, 중앙 계정 | [ldap.md](ldap.md) | OpenLDAP 중앙 계정 저장소 |
| Keycloak, SSO | [keycloak.md](keycloak.md) | 통합 인증 및 SSO |

### 4. Gateway & Access Control

| 주제 | 문서 | 설명 |
|------|------|------|
| OIDC, Zero Trust 게이트웨이 | [oidc-gateway.md](oidc-gateway.md) | OpenResty 기반 Zero Trust 게이트웨이 |

### 5. Observability (로그/모니터링)

| 주제 | 문서 | 설명 |
|------|------|------|
| ELK, 로그 수집·시각화 | [elk.md](elk.md) | ELK Stack 가이드 |

### 6. Medical & AI Data Ops (의료/AI 특화)

| 주제 | 문서 | 설명 |
|------|------|------|
| DICOM, PACS, 의료 영상 | [orthanc.md](orthanc.md) | Orthanc 의료 영상 PACS 서버 |
| 3D Slicer, 이미지 분석 | [slicer.md](slicer.md) | 3D Slicer 가이드 |
| 방사선량 관리 | [openrem.md](openrem.md) | OpenREM 방사선량 관리 플랫폼 |

### 7. 테스트·리포트 (출력물)

| 주제 | 위치 | 설명 |
|------|------|------|
| GS 인증·테스트 리포트 | [test-reports/](test-reports/) | 버전별·일자별 테스트 리포트 (제출용) |

---

## 주요 디렉터리 (코드/설정)

- `templates/`: 서비스별 Docker Compose 템플릿
- `scripts/`: 설치·셋업·백업 등 자동화 스크립트
- `src/`: 주요 소스 코드 (Python/R)
- `config/`: 서비스 설정 파일 (`*.yml`)
- `docs/`: Quarto 렌더링 결과물 (**변경 불가**)

---

이 인덱스는 **ai-agent-guidelines.md Section 4**와 동기화됩니다. 서비스 추가 시 해당 문서를 만든 뒤 이 목록에 반영하세요.
