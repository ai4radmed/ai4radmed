#!/usr/bin/env python3
"""
파일명: scripts/ai4radmed/utils/certs_manager.py
ai4radmed 인증서 관리 모듈 (리팩터링 버전)
주요 기능:
  1. Root CA 생성 및 검증
  2. 서비스별 서버 인증서 생성 (key → csr → crt)
  3. 서비스 인증서의 CA chain 검증
  4. Root CA를 서비스 디렉터리로 복사 (rootCA.crt)
설계 원칙:
  - 각 함수는 단일 책임(SRP)을 유지한다.
  - 상위 함수(create_service_certificate)는 하위 단계를 orchestration 한다.
  - OpenSSL 호출은 subprocess를 통해 수행한다.
  - 경로 구조는 BASE_DIR 및 서비스 이름 기반으로 일관성을 유지한다.
  - 서비스별 key/cert 파일명은 최대한 통일한다.
    * private.key
    * certificate.crt
  - Root CA 원본은 BASE_DIR/certs/ca/rootCA.pem 을 기준으로 관리하고,
    각 서비스 디렉터리에는 복사본(rootCA.crt)만 둔다.
변경이력:
  - 2025-11-19: 최초 구현 시작
  - 2025-11-20: 구조 개선, SAN 기본값 추가
  - 2025-11-20: 서비스별 파일명 통일(private.key/certificate.crt)
  - 2026-01-10: Bitwarden 제거 및 Vaultwarden/Nginx 지원 (간결화)
"""

# Standard library imports
import os
import subprocess
from pathlib import Path
from tempfile import NamedTemporaryFile
from functools import wraps
import yaml

# Third-party imports
from dotenv import load_dotenv
from common.logger import log_info, log_warn, log_error
from common.load_config import load_config
from common.load_config import load_config
from common.load_config import load_config
from common.sudo_helpers import sudo_mkdir, sudo_exists, sudo_check_call

load_dotenv()
PROJECT_ROOT = os.getenv("PROJECT_ROOT")
BASE_DIR = os.getenv("BASE_DIR", "/opt/ai4radmed")
CA_DIR = Path(f"{BASE_DIR}/certs/ca")
CA_KEY = CA_DIR / "rootCA.key"
CA_CERT = CA_DIR / "rootCA.pem"  # 전역 Root CA 인증서 (PEM)


def create_root_ca(overwrite: bool = False) -> bool:
    try:
        if CA_CERT.exists() and CA_KEY.exists() and not overwrite:
            log_info(f"[create_root_ca] Root CA 이미 존재: {CA_CERT}")
            return True

        if not os.path.isdir(CA_DIR):
            if not sudo_mkdir(CA_DIR):
                 log_error(f"[create_root_ca] 디렉토리 생성 실패: {CA_DIR}")
                 return False
            # CA key 생성 전 권한 확보
            user = os.getenv('USER')
            subprocess.run(['sudo', 'chown', '-R', f'{user}:{user}', str(CA_DIR)], check=False)

        log_info("[create_root_ca] Root CA private key 생성 중...")
        subprocess.run(
            ["openssl", "genrsa", "-out", str(CA_KEY), "4096"],
            check=True,
        )

        log_info("[create_root_ca] Root CA self-signed 인증서 생성 중...")
        subprocess.run(
            [
                "openssl",
                "req",
                "-x509",
                "-new",
                "-nodes",
                "-key",
                str(CA_KEY),
                "-sha256",
                "-days",
                "3650",
                "-subj",
                "/C=KR/ST=Seoul/O=ai4radmed/CN=ai4radmed-Root-CA",
                "-out",
                str(CA_CERT),
            ],
            check=True,
        )

        log_info(f"[create_root_ca] Root CA 생성 완료 → {CA_CERT}")
        return True
    except subprocess.CalledProcessError as e:
        log_error(f"[create_root_ca] OpenSSL 호출 실패: {e}")
        return False
    except Exception as e:
        log_error(f"[create_root_ca] 예외 발생: {e}")
        return False

def verify_root_ca() -> bool:
    if not CA_CERT.exists():
        log_warn("[verify_root_ca] Root CA 인증서가 존재하지 않습니다.")
        return False

    try:
        log_info("[verify_root_ca] Root CA 인증서 분석 시작...")
        result = subprocess.run(
            ["openssl", "x509", "-in", str(CA_CERT), "-noout", "-text"],
            capture_output=True,
            text=True,
            check=True,
        )

        preview = result.stdout[:400]
        log_info(f"[verify_root_ca] Root CA 인증서 정보:\n{preview}")
        return True

    except subprocess.CalledProcessError as e:
        log_error(f"[verify_root_ca] OpenSSL 검증 실패: {e.stderr}")
        return False
    except Exception as e:
        log_error(f"[verify_root_ca] 예외 발생: {e}")
        return False

def generate_root_ca_if_needed() -> bool:
    """
    Root CA가 없으면 새로 생성하고, 있으면 그대로 사용
    """
    if CA_CERT.exists() and CA_KEY.exists():
        log_info("[generate_root_ca_if_needed] 기존 Root CA 유지")
        return True

    log_info("[generate_root_ca_if_needed] Root CA 없음 → 새로 생성합니다.")
    return create_root_ca(overwrite=False)

def get_service_cert_paths(service: str) -> tuple[Path, Path, Path]:
    base = Path(BASE_DIR) / service / "certs"
    key_path = base / "private.key"
    csr_path = base / "request.csr"
    cert_path = base / "certificate.crt"
    return key_path, csr_path, cert_path

def build_default_san(service: str) -> str:
    """
    서비스 이름을 기반으로 기본 SubjectAltName 문자열을 구성
    예) postgres → DNS:postgres,DNS:ai4radmed-postgres,IP:127.0.0.1
    """
    project_name = os.getenv("PROJECT_NAME", "ai4radmed")
    dns_entries = [
        service,
        f"{project_name}-{service}",
        f"{service}.{project_name}.internal",
        "localhost",
    ]
    ip_entries = [
        "127.0.0.1",
    ]

    # [Fix] Keycloak Alias Domain Support
    if service == "keycloak":
        dns_entries.append(f"auth.{project_name}.internal")

    san_parts = [f"DNS:{d}" for d in dns_entries] + [f"IP:{ip}" for ip in ip_entries]
    return ",".join(san_parts)

def create_service_key(service: str, key_path: Path) -> bool:
    """
    서비스 private key 생성
    """
    try:
        key_dir = key_path.parent
        key_dir = key_path.parent
        if not os.path.isdir(key_dir):
            if not sudo_mkdir(key_dir):
                log_error(f"[create_service_key] 디렉토리 생성 실패: {key_dir}")
                return False
            user = os.getenv('USER')
            subprocess.run(['sudo', 'chown', '-R', f'{user}:{user}', str(key_dir)], check=False)

        subprocess.run(
            ["openssl", "genrsa", "-out", str(key_path), "4096"],
            check=True,
        )
        log_info(f"[create_service_key] {service} key 생성 완료: {key_path}")
        return True
    except subprocess.CalledProcessError as e:
        log_error(f"[create_service_key] OpenSSL 호출 실패: {e}")
        return False
    except Exception as e:
        log_error(f"[create_service_key] 예외 발생: {e}")
        return False

def create_service_csr(service: str, key_path: Path, csr_path: Path) -> bool:
    """
    서비스 CSR 생성
    """
    try:
        project_name = os.getenv("PROJECT_NAME", "ai4radmed")
        subprocess.run(
            [
                "openssl",
                "req",
                "-new",
                "-key",
                str(key_path),
                "-out",
                str(csr_path),
                "-subj",
                f"/C=KR/ST=Seoul/O=ai4radmed/CN={service}.{project_name}.internal",
            ],
            check=True,
        )
        log_info(f"[create_service_csr] {service} CSR 생성: {csr_path}")
        return True
    except subprocess.CalledProcessError as e:
        log_error(f"[create_service_csr] OpenSSL 호출 실패: {e}")
        return False
    except Exception as e:
        log_error(f"[create_service_csr] 예외 발생: {e}")
        return False

def sign_service_cert_with_ca(
    service: str,
    csr_path: Path,
    cert_path: Path,
    san: str,) -> bool:
    """
    CSR을 Root CA로 서명하여 서버 인증서 생성
    """
    try:
        cert_dir = cert_path.parent
        if not os.path.exists(cert_dir):
             sudo_mkdir(cert_dir)
             user = os.getenv('USER')
             subprocess.run(['sudo', 'chown', '-R', f'{user}:{user}', str(cert_dir)], check=False)

        with NamedTemporaryFile("w", delete=False, suffix=".cnf") as tmp:
            tmp_path = Path(tmp.name)
            tmp.write("[ req ]\n")
            tmp.write("distinguished_name = req_distinguished_name\n")
            tmp.write("req_extensions = v3_req\n")
            tmp.write("[ req_distinguished_name ]\n")
            tmp.write("[ v3_req ]\n")
            tmp.write(f"subjectAltName = {san}\n")

        log_info(
            f"[sign_service_cert_with_ca] {service} cert CA 서명 (SAN={san}) → {cert_path}"
        )

        subprocess.run(
            [
                "openssl",
                "x509",
                "-req",
                "-in",
                str(csr_path),
                "-CA",
                str(CA_CERT),
                "-CAkey",
                str(CA_KEY),
                "-CAcreateserial",
                "-out",
                str(cert_path),
                "-days",
                "365",
                "-sha256",
                "-extensions",
                "v3_req",
                "-extfile",
                str(tmp_path),
            ],
            check=True,
        )

        tmp_path.unlink(missing_ok=True)
        return True

    except subprocess.CalledProcessError as e:
        log_error(f"[sign_service_cert_with_ca] OpenSSL 호출 실패: {e}")
        return False
    except Exception as e:
        log_error(f"[sign_service_cert_with_ca] 예외 발생: {e}")
        return False

def verify_service_cert(service: str, cert_path: Path) -> bool:
    """
    서비스 인증서를 Root CA로 검증
    """
    try:
        result = subprocess.run(
            [
                "openssl",
                "verify",
                "-CAfile",
                str(CA_CERT),
                str(cert_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        log_info(f"[verify_service_cert] OK: {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        log_error(f"[verify_service_cert] 검증 실패: {e.stderr.strip()}")
        return False
    except Exception as e:
        log_error(f"[verify_service_cert] 예외 발생: {e}")
        return False

def deploy_root_ca_to_service(service: str, ca_src: Path) -> bool:
    """
    서비스 디렉터리 내부 certs/에 Root CA 복사
    - 기본 파일명: rootCA.crt
    """
    try:
        cert_dir = Path(BASE_DIR) / service / "certs"
        if not os.path.exists(cert_dir):
             sudo_mkdir(cert_dir)
             user = os.getenv('USER')
             subprocess.run(['sudo', 'chown', '-R', f'{user}:{user}', str(cert_dir)], check=False)
        dst = cert_dir / "rootCA.crt"

        subprocess.run(
            ["cp", "-a", str(ca_src), str(dst)],
            check=True,
        )
        log_info(f"[deploy_root_ca_to_service] Root CA 복사 완료: {dst}")
        return True
    except subprocess.CalledProcessError as e:
        log_error(f"[deploy_root_ca_to_service] 복사 실패: {e}")
        return False
    except Exception as e:
        log_error(f"[deploy_root_ca_to_service] 예외 발생: {e}")
        return False

def resolve_cert_paths(service: str) -> dict:
    """
    인증서 경로를 일원화하여 반환합니다.
    [Updated] 2026-01-19: 보안 강화를 위해 YAML의 path 설정을 더 이상 참조하지 않고
    고정된 경로 구조({BASE_DIR}/{service}/certs)를 사용합니다.
    """
    # directories/files 구조 하드코딩 (Convention over Configuration)
    cert_dir = Path(f"{BASE_DIR}/{service}/certs")
    
    # 파일명 결정 (기본값 고정)
    return {
        "key": cert_dir / "private.key",
        "csr": cert_dir / "request.csr",
        "crt": cert_dir / "certificate.crt",
        "root_ca": cert_dir / "rootCA.crt",
    }

def create_service_certificate(service: str, san: str | None = None) -> bool:
    """
    서비스 인증서 생성:
      1) 경로는 resolve_cert_paths()에서 일원화
      2) key → csr → crt 순 생성
      3) rootCA 복사는 deploy_root_ca_to_service()가 전담
    """
    try:
        # 1) 통합 경로 결정
        paths = resolve_cert_paths(service)
        key_path = paths["key"]
        csr_path = paths["csr"]
        cert_path = paths["crt"]

        # 2) 이미 key + cert 존재하면 skip
        if os.path.exists(key_path) and os.path.exists(cert_path):
            deploy_root_ca_to_service(service, CA_CERT)
            return True

        # 3) SAN 결정
        san_value = san or build_default_san(service)

        # 4) key / csr / crt 생성
        if not create_service_key(service, key_path):
            return False

        if not create_service_csr(service, key_path, csr_path):
            return False

        if not sign_service_cert_with_ca(service, csr_path, cert_path, san_value):
            return False

        if not verify_service_cert(service, cert_path):
            return False

        # [Keycloak Specific] Convert key to PKCS#8 (Der/PEM)
        # Java/JDBC often requires PKCS#8 format for private keys
        if service == "keycloak":
            pk8_path = key_path.with_suffix(".pk8")
            try:
                subprocess.run(
                    [
                        "openssl", "pkcs8", "-topk8", "-inform", "PEM", "-outform", "DER",
                        "-in", str(key_path), "-out", str(pk8_path), "-nocrypt"
                    ],
                    check=True
                )
                log_info(f"[create_service_certificate] Keycloak용 PKCS#8 키 변환 완료: {pk8_path}")
                # Ensure permission
                user = os.getenv('USER')
                subprocess.run(['sudo', 'chown', f'{user}:{user}', str(pk8_path)], check=False)
                subprocess.run(['sudo', 'chmod', '644', str(pk8_path)], check=False) # Keycloak user needs read
            except Exception as e:
                log_error(f"[create_service_certificate] PKCS#8 변환 실패: {e}")
                return False

        # 5) rootCA 복사
        if not deploy_root_ca_to_service(service, CA_CERT):
            return False

        return True

    except Exception as e:
        log_error(f"[create_service_certificate] {e}")
        return False

def apply_service_permissions(service: str) -> bool:
    """
    서비스별 권한(User/Group) 및 파일 모드(600/644/700) 일괄 적용
    
    정책:
      - Postgres: 70:70
      - Vaultwarden/Nginx: 별도 권한이 필요할 경우 추가 대응 (현재는 root 혹은 기본값)
      - 기본: root:root (0:0)
    """
    try:
        cfg_path = f"{PROJECT_ROOT}/config/{service}.yml"
        cfg = load_config(cfg_path) 
        
        # [UID/GID Mapping] 
        # 서비스별로 필요한 UID/GID가 있다면 여기서 설정
        service_ownership = {
            "postgres": (70, 70),
            "elk": (1000, 0),  # Elasticsearch (UID 1000)
            "slicer": (1000, 1000), # 3D Slicer User (UID 1000)
            "vault": (100, 1000),   # Vault User (UID 100)
            "keycloak": (1000, 0),  # Keycloak User (UID 1000), GID 0 (std)
            "ldap": (911, 911),     # OpenLDAP (UID 911)
            # "vaultwarden": (1000, 1000),  # 필요시 활성화
            # "nginx": (101, 101),          # 필요시 활성화
        }
        
        # Default to root (0:0)
        uid, gid = service_ownership.get(service, (0, 0))

        # Mode Settings
        mode_map = {
            "data": "700",  # User only
            "key": "600",   # User read/write
            "cert": "644",  # World readable
            "script": "755" # Executable
        }

        service_dir = Path(BASE_DIR) / service
        path_cfg = cfg.get("path", {})
        dirs = path_cfg.get("directories", {})

        # 1) 주요 디렉터리 경로
        if service == "vault":
            data_dir = Path(dirs.get("data", f"{service_dir}/file")) # [Vault Specific] Use 'file' not 'data'
        else:
            data_dir = Path(dirs.get("data", f"{service_dir}/data"))

        cert_dir = Path(dirs.get("certs", f"{service_dir}/certs"))

        # [Auto-Create] Data 디렉터리가 없으면 생성 (Docker 자동 생성 시 root 소유 되는 문제 방지)
        if not os.path.exists(data_dir):
            subprocess.run(["mkdir", "-p", str(data_dir)], check=False)
        
        # [Special Case] ELK는 하위 데이터 폴더까지 미리 생성해야 함
        if service == "elk":
            for sub in ["elasticsearch", "logstash", "filebeat"]:
                sub_path = data_dir / sub
                if not os.path.exists(sub_path):
                    subprocess.run(["mkdir", "-p", str(sub_path)], check=False)

        # 2) 서비스 루트 소유권 변경
        if service_dir.exists():
            sudo_check_call(["sudo", "chown", "-R", f"{uid}:{gid}", str(service_dir)])
            log_info(f"[apply_service_permissions] 소유권 변경 → {service_dir} ({uid}:{gid})")

        # 3) Data 디렉터리 권한 (700)
        if os.path.exists(data_dir):

            sudo_check_call(["sudo", "chmod", "-R", mode_map["data"], str(data_dir)])
            log_info(f"[apply_service_permissions] data 권한({mode_map['data']}) 적용 → {data_dir}")

        # 4) Cert 디렉터리 권한
        if os.path.exists(cert_dir):
            # [Fix] Ensure directory is accessible (755) so user can traverse
            sudo_check_call(["sudo", "chmod", "755", str(cert_dir)])
            
            # Private Keys (600)
            key_patterns = ["*.key", "*key.pem", "*_key.pem"]
            key_paths = set()
            for pat in key_patterns:
                for p in Path(cert_dir).rglob(pat):
                    key_paths.add(p)
                    sudo_check_call(["sudo", "chmod", mode_map["key"], str(p)])
            
            # Certificates (644) - anything ending in crt/pem excluding keys
            cert_patterns = ["*.crt", "*.pem"]
            for pat in cert_patterns:
                for p in Path(cert_dir).rglob(pat):
                    if p not in key_paths:
                        sudo_check_call(["sudo", "chmod", mode_map["cert"], str(p)])

            log_info(f"[apply_service_permissions] 인증서 파일 권한(Key:600, Cert:644) 정리 완료")

        # 5) 실행 스크립트 권한 (755)
        # 5) 실행 스크립트 권한 (755)
        for script in Path(service_dir).rglob("*.sh"):
            sudo_check_call(["sudo", "chmod", mode_map["script"], str(script)])
            log_info(f"[apply_service_permissions] 스크립트 권한(755) 적용 → {script}")

        log_info(f"[apply_service_permissions] {service} 권한 정리 완료")
        return True

    except Exception as e:
        log_error(f"[apply_service_permissions] 예외 발생: {e}")
        return False

def install_root_ca_windows():
    """
    WSL에서 생성한 Root CA를 Windows 신뢰 저장소에 설치
    - certutil -addstore "Root" rootCA.cer
    """
    root_ca_path = Path("/opt/ai4radmed/certs/ca/rootCA.pem")
    if not root_ca_path.exists():
        print("[ERROR] Root CA 파일이 존재하지 않습니다:", root_ca_path)
        return False

    # Windows %USERPROFILE% 가져오기 (CMD 출력 = cp949)
    try:
        win_home_raw = subprocess.check_output(
            ["cmd.exe", "/c", "echo %USERPROFILE%"],
            stderr=subprocess.DEVNULL,  # UNC 경고 숨김
        )
        win_home = win_home_raw.decode("cp949").strip()
        win_home = win_home.replace("\\", "/")
    except Exception as e:
        print(f"[ERROR] USERPROFILE 경로를 가져오지 못했습니다: {e}")
        return False

    target = f"{win_home}/Downloads/ai4radmed-rootCA.cer"

    # Root CA를 Windows로 복사
    subprocess.run(["cp", str(root_ca_path), f"/mnt/c{target[2:]}"], check=True)
    print(f"[INFO] Root CA 복사 완료 → {target}")

    # certutil로 Root CA를 신뢰 저장소에 추가 (관리자 권한 필요)
    try:
        print("[INFO] 관리자 권한으로 인증서 등록을 시도합니다. (Windows UAC 창이 뜨면 '예'를 눌러주세요)")
        
        # PowerShell Script 생성 (Quoting Hell 방지)
        target_win = target.replace("/", "\\")
        ps_script_content = f"""
        Start-Process certutil -ArgumentList '-addstore "Root" "{target_win}"' -Verb RunAs -Wait
        """
        
        # 임시 ps1 파일 생성 (Windows Downloads 폴더 사용)
        # UNC 경로 문제 해결: CWD가 아닌 절대 경로가 보장된 로컬 경로에 스크립트 생성
        ps_script_name = "install_cert.ps1"
        ps_script_path_linux = f"/mnt/c{win_home[2:]}/Downloads/{ps_script_name}" # Linux Path
        ps_script_path_win = f"{win_home}\\Downloads\\{ps_script_name}".replace("/", "\\") # Windows Path

        with open(ps_script_path_linux, "w") as f:
            f.write(ps_script_content)
            
        # cmd.exe를 통해 powershell 스크립트 실행 -> powershell.exe 직접 실행으로 변경 (Quoting Issue 해결)
        # ExecutionPolicy Bypass 필요
        subprocess.run(
            ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", ps_script_path_win],
            check=True
        )
        
        # 정리
        if os.path.exists(ps_script_path_linux):
            os.remove(ps_script_path_linux)
        
        print("[SUCCESS] 인증서 등록 명령을 보냈습니다. (성공 여부는 Windows 창에서 확인)")
        return True

    except subprocess.CalledProcessError as e:
        print(f"[ERROR] PowerShell(관리자 모드) 실행 실패: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] 예외 발생: {e}")
        return False
