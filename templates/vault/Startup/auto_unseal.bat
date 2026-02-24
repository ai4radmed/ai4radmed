@echo off
timeout /t 30
wsl -d Ubuntu-24.04 -u ben /home/ben/projects/ai4radmed/.venv/bin/python /home/ben/projects/ai4radmed/scripts/ai4radmed/ai4radmed-cli.py setup-host-network
wsl -d Ubuntu-24.04 -u ben /home/ben/projects/ai4radmed/.venv/bin/python /home/ben/projects/ai4radmed/scripts/ai4radmed/ai4radmed-cli.py unseal-vault
