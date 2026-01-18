#!/usr/bin/env python3

import subprocess
import time
import json
import os

from common.logger import log_debug, log_error, log_info, log_warn


VAULT_HEALTH_MAP = {
    200: "OK (initialized, unsealed, active)",
    429: "Standby (initialized, unsealed, standby)",
    472: "DR Secondary",
    473: "Performance Standby",
    474: "Standby but active node unreachable",
    501: "Not initialized",
    503: "Sealed (unsealed required)",
    530: "Node removed from cluster",
}

def check_vault(service: str) -> bool:
    """Vault Health Check via CLI (Docker Exec) - Compatible with Network Segmentation"""
    project_name = os.getenv("PROJECT_NAME", "ai4radmed")
    container = f"{project_name}-{service}"
    # url = "https://localhost:8200/v1/sys/health" # [Changed] 접근 불가

    success_attempt = None
    status_json = None
    
    # [SEC-07] mTLS & [SEC-08] Network Seg 대응
    # 외부(Host)에서 curl 불가 -> 내부 CLI 사용
    cmd = [
        'docker', 'exec', 
        '-u', '100', # [Fix] Run as 'vault' user because root lacks DAC_OVERRIDE (cap_drop: ALL)
        '-e', 'VAULT_ADDR=https://127.0.0.1:8200',
        '-e', 'VAULT_CLIENT_CERT=/vault/certs/certificate.crt',
        '-e', 'VAULT_CLIENT_KEY=/vault/certs/private.key',
        '-e', 'VAULT_CACERT=/vault/certs/rootCA.crt',
        container,
        'vault', 'status', '-format=json'
    ]

    # --------------------------------------------
    # Retry loop
    # --------------------------------------------
    for attempt in range(20):
        try:
            # vault status returns exit code 2 if sealed, 0 if unsealed
            # But we just want the output json
            result = subprocess.run(cmd, capture_output=True, text=True)
            output = result.stdout.strip()
            
            if not output:
                 # Init 안되었거나 에러 시 stderr 확인
                 log_debug(f"[check_vault] status output empty: {result.stderr}")
            else:
                 status_json = json.loads(output)
                 success_attempt = attempt
                 break
                 
        except Exception as e:
            log_debug(f"[check_vault] Exec Error: {e}")

        log_warn(f"[check_vault] CLI 상태확인 실패 → 재시도 ({attempt+1}/20)")
        time.sleep(1)

    if success_attempt is None:
        log_error("[check_vault] 20회 실패 → Vault CLI 응답 없음")
        return False

    # --------------------------------------------
    # 성공 attempt 출력
    # --------------------------------------------
    log_info(f"[check_vault] 상태 확인 성공 → {success_attempt+1}번째 시도")
    
    data = status_json
    log_info(f" initialized: {data.get('initialized')}")
    log_info(f" sealed     : {data.get('sealed')}")
    log_info(f" standby    : {data.get('standby')}")
    log_info(f" version    : {data.get('version')}")

    return True
