#!/usr/bin/env bash
# Oracle Cloud Ampere A1 인스턴스 capacity 자동 재시도 스크립트
# 사용처: Oracle CloudShell (bash, oci CLI 사전 설치됨)

# ============================================================
# 🔧 아래 5개 변수만 본인 값으로 채우세요
# ============================================================
COMPARTMENT_ID="ocid1.tenancy.oc1..aaaaaaaaxqesf77tss27dq7l4k7mqk24bl7r6sv3oysqeaa4lm77ielbjb7q"        # ① Tenancy/Compartment OCID
AVAILABILITY_DOMAIN="UzIj:AP-TOKYO-1-AD-1"      # ② AD 이름 (콜론 포함)
SUBNET_ID="ocid1.subnet.oc1.ap-tokyo-1.aaaaaaaaupzmgynk53wc35luhk5ryl3ie4pwsc2seepovks2atlazosguh2q"  # ③ Public Subnet OCID
IMAGE_ID="ocid1.image.oc1.ap-tokyo-1.aaaaaaaaswhlhdiaseviso3i6c5ozvxldsazmm7kbar6eetg6sijyaclohwa"    # ④ Ubuntu 24.04 ARM Image OCID
SSH_KEY_FILE="$HOME/.ssh/id_ed25519.pub"                # ⑤ 공용키 파일 경로

# ============================================================
# 인스턴스 사양 (필요시 조정)
# ============================================================
DISPLAY_NAME="assist-bot"
SHAPE="VM.Standard.A1.Flex"
OCPUS=2
MEMORY_GB=12
BOOT_VOLUME_GB=50

# ============================================================
# 재시도 정책
# ============================================================
RETRY_INTERVAL_SEC=60       # 시도 사이 대기 시간 (초)
MAX_ATTEMPTS=0              # 0 = 무한 재시도

# ============================================================
# 사양 조합 자동 로테이션 (한 사양만 안 잡힐 때 다른 사양 시도)
# 형식: "OCPU:MEMORY" 공백 구분
# ============================================================
SHAPE_VARIATIONS="2:12 1:6 4:24 1:12 2:6"
USE_ROTATION=true           # true: 시도마다 사양 바꿈, false: 위 OCPUS/MEMORY_GB 고정

# ============================================================
# 로그 파일
# ============================================================
LOG_FILE="$HOME/retry-launch.log"

# ============================================================
set -uo pipefail

log() {
  local msg="$1"
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $msg" | tee -a "$LOG_FILE"
}

bell() {
  for _ in 1 2 3 4 5; do printf '\a'; sleep 0.2; done
}

variations=($SHAPE_VARIATIONS)
var_count=${#variations[@]}
attempt=0
success=false

log "==== 재시도 시작 ===="
log "리전: ${OCI_REGION:-default} | 사양 로테이션: $USE_ROTATION | 간격: ${RETRY_INTERVAL_SEC}s"

while true; do
  attempt=$((attempt + 1))

  if [ "$MAX_ATTEMPTS" -gt 0 ] && [ "$attempt" -gt "$MAX_ATTEMPTS" ]; then
    log "🛑 최대 시도 횟수($MAX_ATTEMPTS) 도달, 종료"
    break
  fi

  if [ "$USE_ROTATION" = true ]; then
    idx=$(( (attempt - 1) % var_count ))
    cur="${variations[$idx]}"
    cur_ocpu="${cur%%:*}"
    cur_mem="${cur##*:}"
  else
    cur_ocpu="$OCPUS"
    cur_mem="$MEMORY_GB"
  fi

  log "🚀 시도 #$attempt | OCPU=$cur_ocpu | RAM=${cur_mem}GB"

  output=$(oci compute instance launch \
    --availability-domain "$AVAILABILITY_DOMAIN" \
    --compartment-id "$COMPARTMENT_ID" \
    --shape "$SHAPE" \
    --shape-config "{\"ocpus\": $cur_ocpu, \"memoryInGBs\": $cur_mem}" \
    --image-id "$IMAGE_ID" \
    --subnet-id "$SUBNET_ID" \
    --assign-public-ip true \
    --ssh-authorized-keys-file "$SSH_KEY_FILE" \
    --display-name "$DISPLAY_NAME" \
    --boot-volume-size-in-gbs "$BOOT_VOLUME_GB" \
    --wait-for-state RUNNING \
    --max-wait-seconds 300 2>&1)
  status=$?

  if [ $status -eq 0 ]; then
    log "✅✅✅ 성공! 인스턴스 생성 완료 (OCPU=$cur_ocpu, RAM=${cur_mem}GB)"
    echo "$output" > "$HOME/launch-success.json"

    public_ip=$(echo "$output" | grep -oP '"public-ip":\s*"\K[^"]+' | head -1)
    if [ -n "${public_ip:-}" ]; then
      log "🌐 공용 IP: $public_ip"
      log "📡 접속 명령: ssh ubuntu@$public_ip"
    fi

    bell
    success=true
    break
  fi

  if echo "$output" | grep -qiE "OutOfHostCapacity|Out of host capacity|capacity"; then
    log "⏳ capacity 부족, ${RETRY_INTERVAL_SEC}초 후 재시도"
  elif echo "$output" | grep -qiE "TooManyRequests|rate"; then
    log "⏳ rate limit, ${RETRY_INTERVAL_SEC}초 후 재시도"
  else
    log "🛑 다른 에러 발생, 중단합니다:"
    echo "$output" | tee -a "$LOG_FILE"
    log "   → OCID/권한/SSH 키 경로를 다시 확인하세요"
    break
  fi

  sleep "$RETRY_INTERVAL_SEC"
done

if [ "$success" = true ]; then
  log "==== 완료: 성공 ===="
  exit 0
else
  log "==== 완료: 실패/중단 ===="
  exit 1
fi
