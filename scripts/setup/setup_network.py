"""
파일명: scripts/setup/setup_network.py
목적: Docker 네트워크 자동 생성
설명: 프로젝트에 필요한 외부 네트워크(public, app, data)를 미리 생성합니다.
"""

import subprocess
import os
import sys

# 프로젝트명을 .env 등에서 가져오거나 하드코딩 (여기선 setup_env.py가 이미 실행되었다고 가정하고 .env 읽기 시도, 혹은 'ai4radmed' 강제)
# setup_env.py 실행 직후라면 .env가 존재함.

def _run_docker(cmd, check=True):
    """Run docker command; on permission denied, retry with sudo (matches make logs pattern)."""
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0:
        return res
    stderr = (res.stderr or "").lower()
    if res.returncode != 0 and "permission denied" in stderr and "docker" in stderr:
        res_sudo = subprocess.run(["sudo"] + cmd, capture_output=True, text=True)
        if res_sudo.returncode == 0:
            return res_sudo
        if check:
            raise subprocess.CalledProcessError(res_sudo.returncode, ["sudo"] + cmd, res_sudo.stdout, res_sudo.stderr)
        return res_sudo
    if check:
        raise subprocess.CalledProcessError(res.returncode, cmd, res.stdout, res.stderr)
    return res

def get_project_name():
    # .env 파일 파싱
    env_path = ".env"
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("PROJECT_NAME="):
                    return line.strip().split("=")[1]
    return "ai4radmed" # Fallback

def create_network(net_name):
    """네트워크 생성 (이미 존재하면 무시)"""
    # 1. 존재 확인
    check_cmd = ["docker", "network", "ls", "--filter", f"name=^{net_name}$", "--format", "{{.Name}}"]
    res = _run_docker(check_cmd, check=False)
    if res.returncode != 0:
        raise subprocess.CalledProcessError(res.returncode, check_cmd, res.stdout, res.stderr)
    if res.stdout.strip() == net_name:
        print(f"[setup_network] {net_name} 이미 존재합니다.")
        return

    # 2. 생성
    print(f"[setup_network] {net_name} 생성 중...")
    create_cmd = ["docker", "network", "create", net_name]
    _run_docker(create_cmd, check=True)

def main():
    project_name = get_project_name()
    
    # 3-Tier Architecture Networks
    networks = [
        f"{project_name}-public", # External Access (Nginx Front)
        f"{project_name}-app",    # Application Logic (Web Apps)
        f"{project_name}-data"    # Data Persistence (DB, Vault)
    ]
    
    # Legacy/Simple/Common network (Optional, if used by some old templates)
    networks.append(f"{project_name}-network") 
    # -> 일부 템플릿(dcmtk 등)에서 ai4radmed(단일) 네트워크를 사용할 수도 있으므로 생성해둠.
    # docker-compose.yml들을 보면 'ai4radmed' 라는 단일 네트워크를 쓰는 녀석들도 있었음 (ldap, elk 등)
    networks.append(project_name) 

    # 중복 제거
    networks = sorted(list(set(networks)))

    print(f"[{sys.argv[0]}] Docker Networks 점검: {networks}")
    
    for net in networks:
        try:
            create_network(net)
        except subprocess.CalledProcessError as e:
            print(f"[setup_network] Error creating {net}: {e}")
            sys.exit(1)

if __name__ == "__main__":
    main()
