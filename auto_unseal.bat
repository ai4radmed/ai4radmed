@echo off
wsl -d Ubuntu -u ben /home/ben/projects/ai4radmed/.venv/bin/python /home/ben/projects/ai4radmed/scripts/ai4radmed/ai4radmed-cli.py unseal-vault
