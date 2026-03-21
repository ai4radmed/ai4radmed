# ai4radmed 아키텍처

이 문서는 AI 에이전트의 **통합 진입점(System Map)**입니다.
모든 작업은 이 문서 → `.spec/` 명세 → `src/` 구현 순서로 수행합니다.

---

## 1. 기술 스택

| 영역       | 기술                                                               |
| ---------- | ------------------------------------------------------------------ |
| 프레임워크 | Python 3.x, R (renv), Docker Compose                               |
| 인프라     | Linux/WSL2, Docker, PostgreSQL, HashiCorp Vault, Keycloak          |
| 네트워킹   | OIDC Gateway (OpenResty), Zero Trust                               |
| 품질       | Pytest (Unit/Integration), GS Certification Standards              |
| 패키지     | uv, renv, Makefile                                                 |
| 로깅       | JSON 구조화 로깅, ELK Stack 연동                                   |

---

## 2. 코드 구조 및 명세 매핑

각 소스 파일은 `.spec/` 디렉터리에 1:1 대응하는 명세를 가집니다.

| 소스 경로         | 명세 경로                   | 역할                        |
| ----------------- | --------------------------- | --------------------------- |
| `src/`            | `.spec/src/*.md`            | 엔진 및 유틸리티 로직       |
| `scripts/`        | `.spec/scripts/*.md`        | 자동화 및 관리 스크립트     |
| `templates/`      | `.spec/templates/*.md`      | Docker Compose 서비스 정의 |
| `config/`         | `.spec/config/*.md`         | 시스템 설정 명세            |
| `tests/`          | `.spec/tests/*.md`          | 테스트 시나리오 및 검증     |

---

## 3. 명세 계층 (Specification Hierarchy)

1. **Level 1 — System Map**: 본 문서. 전체 구조와 정책.
2. **Level 2 — File Spec**: `.spec/` 내 개별 명세. 역할, API, 핵심 규칙.
3. **Level 3 — Implementation**: `src/`, `scripts/`, `templates/` 등 소스 코드 및 `tests/` 테스트.

---

## 4. 개발 워크플로우 (Spec-First)

1. **Plan** — 작업 지시 수령 → 타겟 파일 및 명세 초안 도출.
2. **Manifest** — `.spec/` 하위에 명세 작성/갱신.
3. **Execute** — 명세 기반으로 구현 작성. **구현체 추가/변경 시** 해당 구현체와 **1:1 테스트 명세**를 `.spec/tests/` 하위에 작성하고, 그 명세에 따라 **테스트 구현체**를 `tests/` 하위에 작성한 뒤 **테스트를 실행**한다. 상세 절차는 `.spec/tests/README.md` 참조.
4. **Verify** — 로컬 검증(`make test`) 및 CI 자동 검증.

### 브랜치 전략

- 작업은 **`dev` 브랜치**에서 수행. PR을 통해서만 `origin/main`으로 병합.

### 배포 전 검증 (Makefile)

- `make check-style` → `make test`

---

## 5. 핵심 정책

- **가독성 최우선**: "읽히는 바보 같은 코드"를 지향하며, 적극적인 로깅을 수행합니다.
- **Fail Loudly**: 예외를 삼키지 않고 맥락을 포함한 에러 로그를 남깁니다.
- **보안**: 12 Pillars of World Class Security를 준수하며, Vault 및 OIDC를 통한 제로 트러스트를 구현합니다.
- **테스트**: 모든 기능은 테스트로 증명되어야 하며, GS 인증 기준을 따릅니다.

---

## 6. 상세 참조 문서

| 문서                                                                             | 용도                                                              |
| -------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| [.spec/tests/README.md](.spec/tests/README.md)                                   | **구현체당 테스트 명세 1:1 작성 절차** 및 테스트 구현체 생성 규칙 |
| [DEVELOPERS.md](documents/DEVELOPERS.md)                                           | 개발자를 위한 상세 시스템 개요 및 가이드 (Non-Agent)              |
| [ai-agent-guidelines.md](documents/ai-agent-guidelines.md)                       | AI 에이전트 공통 원칙 및 코딩 철학                                |
| [security-implementation-plan.md](documents/security-implementation-plan.md)     | 보안 구현 계획 및 12 Pillars 체크리스트                          |
| [operations.md](documents/operations.md)                                         | 운영 및 배포 가이드                                               |
| [postgres.md](documents/postgres.md)                                             | 데이터베이스 서비스 명세                                          |
| [vault.md](documents/vault.md)                                                   | 보안 키 및 시크릿 관리 명세                                       |
