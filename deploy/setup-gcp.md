# GCP e2-micro 셋업 (Always Free)

무료 조건: e2-micro, us-west1/us-central1/us-east1, 표준 영구디스크 30GB 이하.

## 1. 인스턴스 생성 (로컬 gcloud 또는 콘솔)

```bash
gcloud compute instances create assist-bot \
  --zone=us-west1-b --machine-type=e2-micro \
  --image-family=ubuntu-2404-lts-amd64 --image-project=ubuntu-os-cloud \
  --boot-disk-size=30GB --boot-disk-type=pd-standard
```

## 2. 기본 셋업 (ssh 접속 후)

```bash
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile \
  && sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
sudo apt update && sudo apt install -y python3-venv git curl
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash - \
  && sudo apt install -y nodejs
sudo npm install -g @anthropic-ai/claude-code
sudo useradd -m -s /bin/bash assist
```

## 3. 코드 배치

```bash
sudo git clone https://github.com/keemminxu/Assist.git /opt/assist
sudo chown -R assist:assist /opt/assist
sudo -u assist python3 -m venv /opt/assist/.venv
sudo -u assist /opt/assist/.venv/bin/pip install -r /opt/assist/requirements.txt
```

## 4. 인증

```bash
sudo -u assist claude setup-token   # 브라우저 URL 안내 따라 진행 (Max 구독 장기 토큰)
# 발급된 토큰을 /opt/assist/.env 에 CLAUDE_CODE_OAUTH_TOKEN=... 으로 추가
# 로컬 .env의 나머지 값(DISCORD_TOKEN 등)도 /opt/assist/.env 로 복사
sudo chmod 600 /opt/assist/.env && sudo chown assist:assist /opt/assist/.env
```

## 5. 서비스 등록

```bash
sudo cp /opt/assist/deploy/assist-bot.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now assist-bot
systemctl status assist-bot     # active (running) 확인
journalctl -u assist-bot -f     # "비서 봇 가동" 로그 확인
```

## Oracle A1 이전 (capacity 확보 시)

1. PAYG 전환(무료 한도 유지, capacity 거절 해소) 후 OCI 콘솔 → Billing → **Budgets에서 월 $1 알림** 설정
2. Oracle CloudShell에서 `oci-retry/retry-launch.sh` 실행해 A1 확보
3. A1 인스턴스에 위 2~5단계 동일 적용 (ARM이지만 절차 동일)
4. GCP의 `/opt/assist/.env` 를 그대로 복사
5. A1에서 `systemctl enable --now assist-bot` → Discord 대화 검증
6. GCP 쪽 `sudo systemctl disable --now assist-bot`
7. 24시간 병행 관찰 후 GCP 인스턴스 삭제:
   `gcloud compute instances delete assist-bot --zone=us-west1-b`
