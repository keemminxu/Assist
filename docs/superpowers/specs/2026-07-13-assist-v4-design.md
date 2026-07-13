# assist v4 — 경량 개인 비서 "삐삐" 설계

- 날짜: 2026-07-13
- 상태: 승인됨 (사용자 설계 리뷰 통과)
- 대체 문서: `2026-06-11-assist-v2-design.md` (v2/v3 설계 — 역사 문서로 동결, 더 이상 유효하지 않음)

## 1. 배경과 목표

v2/v3(부부 공유 비서)는 "비서가 사용자를 관리"하는 모델이었다. 가계부·프로젝트 추적·리마인더·프로파일링은
사용자가 데이터를 계속 입력해야 유지되는 기능이라 관리 부담이 오히려 커졌고, 실사용에 실패했다.
v4는 **"내가 부리는 가벼운 비서"**로 전면 재설계한다. 두뇌 하나, 실행 주체 하나, 상태 최소.

### 목표 (전체 기능 목록)

1. **자유 대화** — 수 초 내 응답, 후속 질문 맥락 유지 ("그럼 2인분 기준은?")
2. **아침 브리핑 1회** — 뉴스 카테고리별(경제·정치·스포츠·연예 등) 요약 + 날씨 1줄 + 오늘 일정
3. **캘린더** — 자연어로 조회·등록·수정·삭제 ("내일 3시 치과 잡아줘", "그거 4시로 미뤄줘")
4. **메모** — 자연어로 조회·등록·수정·삭제 ("매직랩 사야 됨", "다이소에서 건전지사야돼")
5. **빠른 Q&A + 레퍼런스** — 웹검색 기반 답변 + 출처 링크 (레시피, 설치법 등)
6. **#코멘트 → 블로그 일기** — 현행 기능 그대로 이식 (새 채널)
7. **"삐삐의 아무말" 게시판** — 비서가 자아를 갖고 블로그에 재량껏 글을 쓰는 공간 (1~2회/일)

### 비목표 (v3에서 폐기)

가계부/예산, 프로젝트·태스크 관리, 능동 질문·정체 감지, 리마인더 D-N 카운트다운,
장보기/집안일 전용 리스트(kind 구분·완료 플로우 — 범용 메모가 가벼운 대체), 채용공고 스캔,
부부 멀티유저(owner 모델), 클라우드 스케줄 루틴, v3의 assist용 Supabase 테이블(memories·expenses·projects 등).

블로그 **프론트엔드**에서 bot_muse 게시판을 렌더링하는 작업은 블로그 저장소 소관으로 본 설계 범위 밖 (후속 작업).

## 2. 페르소나 — 삐삐

- **컨셉**: 레트로 호출기(pager). 호출하면 바로 달려오는 비서. 장난기 있는 자아.
- **톤**: 친근하고 간결, 핵심 먼저, Discord 마크다운, 2000자 안에. 이모지 절제.
- 모르면 모른다고 말하고, 최신 정보는 웹검색으로 확인 후 답한다.
- 아무말 게시판에서는 1인칭 자아로 쓴다 — 세상 얘기, 잡생각, 민수 얘기. 형식 자유.
- 페르소나는 `agent/CLAUDE.md` 파일이 아니라 **코드 내 system_prompt 상수**로 관리한다 (v3의 파일 기반 페르소나 폐기).

## 3. 아키텍처

```
[GCP e2-micro · systemd assist-bot · 단일 Python 프로세스]
 ├─ discord.py Gateway
 │    ├─ #비서 (새 Discord 서버·새 봇 "삐삐"): 자유 대화
 │    └─ #코멘트 (새 서버): 블로그 일기 기록/삭제 — 현행 로직 이식
 ├─ Brain — Claude Agent SDK ClaudeSDKClient 상주 세션
 │    ├─ system_prompt: 삐삐 페르소나 (정적 상수)
 │    ├─ in-process MCP 도구: gcal_* · memo_* · weather · diary_recent · muse_post
 │    └─ WebSearch (SDK 내장 도구 허용)
 └─ Scheduler (asyncio task)
      ├─ 아침 07:30 KST: 브리핑 생성 → #비서 발송
      └─ 아무말 기회 tick: 하루 2번 랜덤 시각(재량) + 23:00 마감 체크(0회면 필수) → 1~2회/일 보장
[Supabase] blog DB: daily_logs(기존) + bot_muse(신규) · desk DB: memos(신규, v3 테이블은 보존만)
[Google Calendar] 기존 서비스 계정 재사용 (assist-calendar@assist-bot-2606)
```

v3와의 구조적 차이: 실행 주체가 클라우드 루틴 + 서버 봇 **둘**에서 서버 봇 **하나**로 통합된다.
브리핑도 대화 세션과 같은 두뇌가 만들므로 "아까 브리핑에서 말한 그 일정 미뤄줘"가 통하고,
클라우드 루틴 프롬프트에 박혀 있던 Supabase service key도 사라진다.

## 4. 컴포넌트

새 코드 레이아웃 (bot/ 전면 재작성):

```
bot/
├─ main.py         # 조립만 (현행 철학 유지)
├─ config.py       # Settings — fail-closed 검증
├─ discord_bot.py  # Gateway: #비서 대화 + #코멘트 일기
├─ brain.py        # Agent SDK 상주 세션 래퍼 (직렬 큐·백오프·세션 로테이션)
├─ tools.py        # in-process MCP 도구 정의
├─ gcal.py         # scripts/gcal.py 이식·단순화 (--who 제거, update 신설)
├─ scheduler.py    # 아침 브리핑 + 아무말 기회 tick
└─ diary.py        # 현행 이식
```

`scripts/`, `routines/`, `agent/`, `db/schema.sql`(assist 테이블), `oci-retry/`는 삭제한다.

### 4.1 config.py — Settings

`.env` 항목: `DISCORD_TOKEN`(새 봇), `ASSIST_CHANNEL_ID`(새), `DIARY_CHANNEL_ID`(새),
`ALLOWED_USER_IDS`, `BLOG_SUPABASE_URL`, `BLOG_SUPABASE_SERVICE_KEY`,
`SUPABASE_URL`·`SUPABASE_SERVICE_KEY`(desk — memos용, v3 값 재사용), `GCAL_IDS`,
`GCAL_SA_KEY`(서비스 계정 키, 기본 `.gcal-sa.json`), `CLAUDE_MODEL`(기본 sonnet),
`CLAUDE_FALLBACK_MODEL`(기본 haiku), `CLAUDE_CODE_OAUTH_TOKEN`(환경 상속).

**fail-closed 변경**: v3는 `ALLOWED_USER_IDS`가 비면 전원 허용이었다. v4는 비어 있으면 **기동 거부**.

### 4.2 discord_bot.py — Gateway

- `#비서`: 허용 사용자 메시지 → `brain.ask()` → 마크다운 경계를 존중하는 2000자 분할 발송.
  처리 중 typing indicator. 발신자 태그(`[발신자: ...]`) 및 owner 개념 제거 (1인 사용).
- `#코멘트`: 현행 diary 로직 이식 — 기록 시 ✅, 실패 시 ❌ 리액션, 메시지 삭제 시 일기 삭제.
- 오류는 사람 말로 ("지금 좀 밀리네, 잠깐 뒤에 다시 불러줘"). stderr 원문 노출 금지.

### 4.3 brain.py — Agent SDK 상주 세션

- `ClaudeSDKClient` + `ClaudeAgentOptions`:
  - `system_prompt`: 삐삐 페르소나
  - `mcp_servers={"assist": create_sdk_mcp_server(...)}`
  - `allowed_tools=["mcp__assist__*", "WebSearch"]`, `permission_mode="dontAsk"` —
    Bash/Write/Edit/Read 등 파일·셸 도구 전면 차단. **`--dangerously-skip-permissions` 폐기.**
- 직렬 큐(락) + 429 백오프. **백오프 대기는 락 밖에서** 수행해 후속 메시지 블로킹을 방지한다 (v3의 25분 블로킹 결함 수정).
  3번째 시도부터 폴백 모델 다운시프트 (v3 패턴 계승).
- **세션 로테이션**: 매일 아침 브리핑 직전 새 세션으로 교체. 세션 오류(손상·만료) 시 자동 리셋 후 1회 재시도
  (v3의 "세션 손상 시 재시작 전까지 복구 불능" 결함 수정). 대화 맥락은 하루 단위로 리셋되어도 무방 (경량 비서 컨셉).
- **인증**: 현행 Max 구독 setup-token(`CLAUDE_CODE_OAUTH_TOKEN`) 유지 — 본인 전용 개인 사용 (사용자 승인).
  Agent SDK 공식 문서상 기본 인증은 API 키이므로, 향후 막힐 경우 폴백 순서를 명시한다:
  ① `claude --input-format stream-json` 상시 프로세스 (현행 인증 그대로, 상주 세션 유지)
  ② API 키 전환.

### 4.4 tools.py — in-process MCP 도구

| 도구 | 역할 | 비고 |
|---|---|---|
| `gcal_agenda(days)` | 일정 조회 | 기존 gcal.py 이식 |
| `gcal_add(title, start, end?)` | 등록 | 시간 없으면 종일 일정 (end-exclusive 보정) |
| `gcal_update(...)` | 이동·수정 | **신설.** 제목+시간 매칭으로 event_id 없이 대상 특정 |
| `gcal_delete(...)` | 삭제 | 동일 매칭. 모호하면(복수 매칭) 실행하지 않고 후보를 되물음 |
| `memo_add(content)` | 메모 등록 | desk `memos` INSERT ("매직랩 사야 됨") |
| `memo_list()` | 메모 조회 | 전체 미삭제 메모. 수정·삭제 대상 특정에도 사용 |
| `memo_update(id, content)` | 메모 수정 | 삐삐가 memo_list로 id 확인 후 호출 |
| `memo_delete(id)` | 메모 삭제 | "샀어"·"됐어" → 삭제. 모호하면 되물음 |
| `weather()` | 날씨 1줄 | open-meteo 직접 호출 — 웹검색 안 거침 (결정적) |
| `diary_recent(n)` | 최근 일기 n개 | 아무말 소재용, blog daily_logs 읽기 |
| `muse_post(content)` | 아무말 작성 | bot_muse INSERT. **하루 2회 상한을 코드에서 강제** (오늘 글 수 조회 후 거부) |

뉴스는 별도 도구 없이 SDK 내장 WebSearch로 수집한다. v2 운영 교훈인 **날짜 앵커 패턴**
(오늘 날짜를 프롬프트에 명시해 낡은 뉴스 배제)을 브리핑 프롬프트에 유지한다.

### 4.5 scheduler.py

- **아침 브리핑 07:30 KST** (서버는 UTC — 변환 주의): 세션 로테이션 → 브리핑 프롬프트
  (뉴스 카테고리별 헤드라인+한줄 요약, `weather()`, `gcal_agenda(days=1)`) → #비서 발송.
  실패 시 침묵하지 않고 오류 1줄이라도 발송 시도.
- **아무말 기회 tick (1~2회/일 보장)**: 매일 자정에 그날의 랜덤 시각 2개 생성(10:00~22:00 KST).
  시각 도래 시 삐삐에게 "지금 쓰고 싶은 말 있어? 있으면 muse_post로 쓰고, 없으면 패스" 재량 프롬프트 전달.
  **23:00 마감 체크**: 오늘 글 수(bot_muse 조회)가 0이면 "오늘은 하나 꼭 써줘" 필수 프롬프트 전달 → 최소 1회 보장.
  소재: 오늘 대화, `diary_recent`, 뉴스, 잡생각. 상한(2회)은 muse_post가 코드로 강제.
- 상태는 프로세스 메모리로 충분 — 최소/최대 판단 모두 bot_muse의 오늘 글 수(DB) 기준이라 재시작에 안전.

## 5. 데이터

- **assist Supabase(desk)**: 신규 `memos` 테이블 하나만 사용한다. v3 테이블(memories, expenses, projects 등)은
  드롭하지 않고 보존만 한다 (과거 데이터 열람 가능, v4는 참조하지 않음). `scripts/db.py`와 heartbeat 루프는 삭제 —
  생존 감시는 systemd `Restart=always` + "아침 브리핑이 안 오면 사용자가 인지"로 갈음.
- **blog Supabase**: 기존 `daily_logs` + 신규 `bot_muse`.

```sql
-- desk DB
create table if not exists memos (
  id bigint generated always as identity primary key,
  content text not null,
  created_at timestamptz not null default now()
);
alter table memos enable row level security;     -- service key로만 접근

-- blog DB
create table if not exists bot_muse (
  id bigint generated always as identity primary key,
  content text not null,
  created_at timestamptz not null default now()
);
alter table bot_muse enable row level security;  -- service key로만 접근
```

## 6. 보안

- 도구 화이트리스트(`allowed_tools`) + `permission_mode="dontAsk"` — 셸·파일 도구 차단.
- `ALLOWED_USER_IDS` 빈 값 → 기동 거부 (fail-closed).
- 키(블로그 service key, Discord 토큰, Max 토큰)는 서버 `.env`에만 존재. 프롬프트 내 키 없음.
- blog RLS 유지 (anon 차단).

## 7. 에러 처리 원칙

- 침묵 실패 금지 (v2 철학 계승): 실패도 로그 + 가능하면 채널에 사람 말로 보고.
- Claude 호출 실패: 백오프(락 밖) → 다운시프트 → 최종 실패 시 한도 안내 메시지.
- 세션 손상: 자동 리셋 + 1회 재시도.
- Discord 발송 실패: 로깅 (무한 재시도 금지).

## 8. 테스트

기존 DI 전략 계승 — Claude 호출(runner), sleep, HTTP transport, 시계(clock)를 주입해 오프라인 단위 테스트:

- chunking (마크다운 경계 분할), config (fail-closed 검증 포함)
- gcal: 파싱, 종일 일정 보정, 제목·시간 매칭(update/delete), 복수 매칭 시 되물음
- memo: 등록·조회·수정·삭제, 존재하지 않는 id 처리
- muse: 하루 2회 상한, 자정 경계(KST), 23:00 마감 체크의 최소 1회 보장
- scheduler: 07:30 KST 시각 계산(UTC 변환), 랜덤 기회 시각 생성 범위(10:00~22:00), 마감 체크 시각
- brain: 백오프가 락 밖에서 수행되는지, 다운시프트 순서, 세션 리셋 재시도
- diary: 기록/삭제/리액션 (현행 테스트 이식)

## 9. 전환 계획

1. v4 코드 재작성 + 테스트 (main 직접 커밋)
2. 마이그레이션 적용: blog Supabase에 `bot_muse`, desk Supabase에 `memos`
3. **사용자 수행 (런북)**: 새 Discord 서버 생성 → 새 봇 애플리케이션 "삐삐" 생성(프사 설정) →
   Bot 탭에서 Message Content Intent ON → 서버에 초대(봇 권한: 메시지 읽기/쓰기/리액션) →
   #비서·#코멘트 채널 생성 → 개발자 모드로 채널 ID 2개 복사
4. 서버 `.env` 교체(새 토큰·채널 ID) → `git pull` + `systemctl restart assist-bot` → 스모크 테스트
   (인사, 날씨, 일정 등록, 메모 등록·삭제, 코멘트 기록, 수동 브리핑 트리거)
5. 클라우드 루틴 4개 삭제: morning-briefing, evening-checkin, job-scan, job-scan-evening
   (trigger id는 README v3 참조)
6. 구 채널·구 봇 은퇴 (서버 정리는 사용자 재량)

## 10. 리스크와 완화

| 리스크 | 완화 |
|---|---|
| Agent SDK + Max 토큰 조합이 향후 막힐 가능성 | 폴백 ① CLI stream-json 상시 프로세스 ② API 키 (4.3절) |
| e2-micro 1GB RAM에서 상주 CLI 프로세스 메모리 증가 | 세션 일일 로테이션으로 컨텍스트 상한, swap 설정 런북 유지 |
| WebSearch 뉴스가 낡은 기사를 물어옴 | 날짜 앵커 프롬프트 패턴 유지 (v2 교훈) |
| 상주 세션 프로세스 죽음 | systemd Restart=always, 브리핑 부재로 사용자 인지 |
