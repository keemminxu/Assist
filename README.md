# assist v2 — 24시간 개인 비서

Discord로 소통하는 개인 비서. 정기 작업(아침 브리핑·채용공고 스캔·저녁 체크인)은
Claude Code **클라우드 스케줄 에이전트**가 서버 없이 수행하고, 자유 대화는
무료 서버(GCP e2-micro → Oracle A1)의 얇은 discord.py 봇이 `claude -p` 헤드리스
호출로 처리한다. 기억은 Supabase 무료 Postgres 한 곳에 모은다.

```
[Anthropic 클라우드 — 서버 0대]            [GCP e2-micro (무료) → Oracle A1 (잡히면 이전)]
 스케줄 에이전트 (routines)                  Discord 대화 봇 (Python, 얇은 릴레이)
  ├─ 아침 브리핑 (메일+일정)   07:30          ├─ 메시지 수신 → claude -p 헤드리스 호출
  ├─ 채용공고 스캔 (언리얼)    09:00          ├─ 직렬 큐 + 429 백오프 + 모델 다운시프트
  └─ 저녁 체크인 (내일일정+식단) 21:00        └─ systemd 상시 구동, Max 구독 토큰 인증
       │                                          │
       └──── Discord Webhook ───→ [Discord 채널] ←─ Gateway ─┘

              [Supabase 무료 Postgres] ← 양쪽이 같은 DB를 공유 = "하나의 기억"
```

## 구성 요소

| 위치 | 역할 |
|---|---|
| `routines/` | 클라우드 루틴 프롬프트 원본 (`/schedule`로 등록 — 파일 수정 후 재등록 필요) |
| `bot/` | Discord 대화 봇 (엔트리: `python -m bot.main`) |
| `agent/CLAUDE.md` | 비서 페르소나 — `claude -p` 가 이 디렉토리에서 실행됨 |
| `scripts/db.py` | 비서(Claude)가 Bash로 호출하는 Supabase CLI |
| `db/schema.sql` | 테이블 5개: memories, meals, job_postings, schedule_notes, heartbeat |
| `deploy/` | systemd 유닛 + GCP/Oracle 셋업 절차 |
| `oci-retry/` | Oracle A1 capacity 재시도 스크립트 (v1에서 유지) |

## 로컬 실행

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env   # 값 채우기
.venv/Scripts/python -m pytest        # 16개 테스트
.venv/Scripts/python -m bot.main      # 봇 기동
```

## 운영 런북

- **봇 재시작**: `sudo systemctl restart assist-bot`
- **로그**: `journalctl -u assist-bot -f`
- **루틴 수정**: `routines/*.md` 수정 → Claude Code에서 `/schedule`로 해당 루틴 업데이트
- **봇 생존 확인**: Supabase `heartbeat` 테이블 — 30분 무신호면 저녁 체크인이 Discord로 알림
- **새 테이블 추가**: `db/schema.sql`에 추가 → Supabase MCP `apply_migration`으로 적용
- **429 빈발 시**: `.env`의 `CLAUDE_MODEL`을 `haiku`로 낮추거나 루틴 빈도 축소

### 클라우드 루틴 인프라 (등록 완료, 관리: https://claude.ai/code/routines)

| 루틴 | trigger_id | 스케줄 (KST/UTC) |
|---|---|---|
| morning-briefing | `trig_01JWDRtXgMXptKPd5BJ2fCtP` | 07:30 / 22:30 전날 |
| job-scan | `trig_015kcr2dP6UxQ99mKfqdjyR9` | 09:00 / 00:00 |
| evening-checkin | `trig_016UduhHxdsGu2awFjQCrzjF` | 21:00 / 12:00 |

- **전용 클라우드 환경**: `assist` (`env_014a4KJoj4zmVsH3xAS5gwqS`) — 네트워크 "사용자 정의"
  허용 도메인: discord(app).com, wanted/jobkorea/gamejob/saramin.co.kr, supabase.co (+ 와일드카드)
- **교훈 두 가지** (둘 다 침묵 실패의 원인이었음):
  1. 기본(Default) 환경은 "신뢰됨" 네트워크라 discordapp.com 아웃바운드 차단 → 루틴은 반드시 assist 환경에서
  2. Discord webhook은 기본 curl User-Agent를 403으로 차단 → `-H "User-Agent: assist-routine/1.0"` 필수
- **Supabase 프로젝트**: `tuqwhjldzghnsenyhyom` (이름 desk, ap-southeast-2)

## 문서

- 설계: `docs/superpowers/specs/2026-06-11-assist-v2-design.md`
- 구현 계획: `docs/superpowers/plans/2026-06-11-assist-v2.md`
- 채용 사이트 수집 전략: `docs/superpowers/research/2026-06-11-job-sites.md`
