#!/usr/bin/env bash
# assist 봇 서버 프로비저닝 (Ubuntu 24.04, root로 실행)
# 사용: curl -fsSL https://raw.githubusercontent.com/keemminxu/Assist/main/deploy/provision-server.sh | sudo bash
set -euo pipefail

echo "== 1/6 스왑 2G (저메모리 인스턴스 보강) =="
if ! swapon --show | grep -q /swapfile; then
  fallocate -l 2G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

echo "== 2/6 기본 패키지 =="
export DEBIAN_FRONTEND=noninteractive
apt-get update -y -q
apt-get install -y -q python3-venv git curl

echo "== 3/6 Node 22 + Claude Code CLI =="
if ! command -v node >/dev/null 2>&1 || [[ "$(node -v)" != v22* ]]; then
  curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
  apt-get install -y -q nodejs
fi
npm install -g @anthropic-ai/claude-code

echo "== 4/6 전용 사용자 assist =="
id assist >/dev/null 2>&1 || useradd -m -s /bin/bash assist

echo "== 5/6 코드 배치 =="
if [[ ! -d /opt/assist ]]; then
  git clone https://github.com/keemminxu/Assist.git /opt/assist
else
  git -C /opt/assist pull
fi
chown -R assist:assist /opt/assist
sudo -u assist python3 -m venv /opt/assist/.venv
sudo -u assist /opt/assist/.venv/bin/pip install -q -r /opt/assist/requirements.txt

echo "== 6/6 systemd 유닛 등록 (시작은 .env 업로드 후) =="
cp /opt/assist/deploy/assist-bot.service /etc/systemd/system/
systemctl daemon-reload

echo "프로비저닝 완료. 다음: /opt/assist/.env 업로드(0600, assist 소유) 후 'systemctl enable --now assist-bot'"
