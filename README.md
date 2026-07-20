# assist v4 — 경량 개인 비서 "삐삐"

Discord로 부리는 개인 비서. 단일 Python 프로세스(GCP e2-micro)가
Claude Agent SDK 상주 세션으로 대화·아침브리핑·캘린더·메모·블로그 게시판을 처리한다.
설계: `docs/superpowers/specs/2026-07-13-assist-v4-design.md`
(muse 격리 개정: `docs/superpowers/specs/2026-07-20-muse-isolation-design.md`)

## 기능

1. 자유 대화 + 웹검색 레퍼런스
2. 아침 브리핑(뉴스·날씨·오늘 일정) 07:30 KST
3. 캘린더 조회·등록·수정·삭제 (자연어)
4. 메모 CRUD
5. #코멘트 → 블로그 일기
6. 삐삐의 블로그 게시판 (bot_muse, 1~2회/일 — 랜덤 기회 2번 + 23시 마감 체크).
   **뉴스·날씨 견해 전용** — 대화와 격리된 전용 세션(muse_brain)에서 빈 컨텍스트로 쓴다.
   muse 서버엔 사적 도구(gcal·memo·diary) 미등록, 대화 서버엔 muse_post 미등록,
   + 개인 정보 금지 페르소나 (2026-07-20 개편)

## 구조

`bot/main.py`(조립) · `config`(fail-closed) · `discord_bot`(게이트웨이) · `brain`(Agent SDK 상주 세션,
백오프·다운시프트·세션 로테이션) · `tools`(in-process MCP 도구 11종) · `gcal` · `store`(memos·bot_muse) ·
`weather` · `scheduler` · `prompts`(삐삐 페르소나) · `diary`(v3 이식)

## 로컬 실행

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env   # 값 채우기
.venv/Scripts/python -m pytest        # 79개 테스트
.venv/Scripts/python -m bot.main
```

## 새 Discord 서버/봇 셋업 (1회)

1. Discord 서버 새로 만들기 → #비서, #코멘트 채널 생성
2. discord.com/developers → New Application "삐삐" → Bot 탭:
   프사 업로드, MESSAGE CONTENT INTENT ON, 토큰 복사(`DISCORD_TOKEN`)
3. OAuth2 → URL Generator: scope=bot, 권한 View Channels/Send Messages/Add Reactions
   → 생성된 URL로 서버에 초대
4. Discord 설정 → 고급 → 개발자 모드 ON → 채널 우클릭 → ID 복사 → `.env`에
5. 본인 유저 ID 복사 → `ALLOWED_USER_IDS`

## 운영 런북

- 서버: `gcloud compute ssh assist-bot --zone=us-west1-b`
- 배포: `cd /opt/assist && sudo -u assist git pull && sudo systemctl restart assist-bot`
- 로그: `journalctl -u assist-bot -f`
- Max 토큰 만료 시: `claude setup-token` 재발급 → `/opt/assist/.env`
- 브리핑이 안 오면 봇이 죽은 것 → systemd `Restart=always`가 재기동, 로그 확인
- GCP 무료체험 2026-09-11 만료 — 이전에 유료 계정 업그레이드(e2-micro는 Always Free라 $0)

## v3 정리 체크리스트 (전환 시 1회)

- [ ] desk Supabase에 `db/v4-memos-desk.sql` 적용 (Supabase MCP `apply_migration`)
- [ ] blog Supabase에 `db/v4-bot-muse-blog.sql` 적용
- [ ] 클라우드 루틴 4개 삭제: `trig_01JWDRtXgMXptKPd5BJ2fCtP`(morning) ·
      `trig_016UduhHxdsGu2awFjQCrzjF`(evening) · `trig_015kcr2dP6UxQ99mKfqdjyR9`(job) ·
      `trig_01UHBnqRTauyaYeF7CVFraEq`(job-evening) — https://claude.ai/code/routines
- [ ] 서버 `/opt/assist/.env` 를 새 `.env.example` 기준으로 교체 (v3 잔여 키 제거)
- [ ] 서버에서 `pip install -r requirements.txt` (claude-agent-sdk 설치)
- [ ] 스모크 테스트: 인사 → 날씨 → "내일 3시 치과" 등록 → "치과 4시로" 수정 → 메모 등록/삭제 → #코멘트 기록
- [ ] 구 채널·구 봇 은퇴

## 리스크 메모

- Agent SDK 인증은 현행 Max setup-token(개인 사용). 문제 발생 시 폴백:
  ① `claude` CLI `--input-format stream-json` 상시 프로세스 ② API 키
