# muse 격리 — 아무말 게시판을 뉴스·날씨 견해 채널로 개편

- 날짜: 2026-07-20
- 상태: 승인됨 (사용자 결정: "뉴스·날씨 견해 채널로 개편" + 기존 글 전부 삭제)
- 개정 대상: `2026-07-13-assist-v4-design.md`의 아무말 게시판(§4.5 muse) 부분

## 1. 배경 — 사고

v4의 muse는 대화 세션과 **같은 두뇌**(brain)에서 실행됐고, 페르소나가 "오늘 민수와 나눈
대화, 민수의 최근 일기"를 소재로 권장했다. 그 결과 공개 블로그(keemminxu.com/pippi)에
실명·가족 일정·달력 내용·구매 검토·보안 관련 일화가 그대로 게시됐다.
2026-07-20에 기존 글 9개를 전부 삭제하고 구조를 개편했다.

원인 3가지:
1. **세션 공유** — muse 프롬프트가 하루치 대화가 쌓인 상주 세션에서 실행됨
2. **프롬프트가 사적 소재 권장** — "민수와 나눈 대화, 일기(diary_recent)"
3. **강제 마감** — 23시에 글이 없으면 무조건 쓰게 해, 안전한 소재가 없어도 대화에서 끌어옴

## 2. 원칙 — 금지보다 격리

"사적인 얘기 쓰지 마"라는 규칙만으로는 모델이 한 번만 실수해도 공개된다.
**muse 세션에는 사적 컨텍스트가 애초에 존재하지 않게 한다.** 금지 규칙은 이중 안전장치.

## 3. 구조

```
[대화 brain]  PERSONA        + build_server(10종, muse_post 미등록) + CHAT_ALLOWED_TOOLS(muse_post 제외)
[muse brain]  MUSE_PERSONA   + build_muse_server(muse_post·weather만) + MUSE_ALLOWED_TOOLS
                └ 매 호출 ask_fresh() — rotate 후 질의, 빈 세션 보장
```

격리 4겹 — 양방향 모두 서버 등록 + allowed_tools 이중 차단:
1. **별도 Brain/세션** — muse는 대화 이력이 없는 전용 두뇌. `ask_fresh()`가 매번 세션을
   비우고 시작하므로 이전 muse 글의 맥락도 안 남는다.
2. **서버 차원 도구 제거** — `build_muse_server`는 muse_post·weather만 등록해 muse 세션엔
   gcal·memo·diary_recent가 아예 없고, 반대로 `build_server`는 muse_post를 등록하지 않아
   사적 데이터를 읽는 대화 세션은 공개 블로그에 글을 쓸 수 없다.
3. **allowed_tools 화이트리스트** — `MUSE_ALLOWED_TOOLS = [muse_post, weather, WebSearch]`,
   `CHAT_ALLOWED_TOOLS`는 muse_post 제외. 서버 등록과 독립인 두 번째 층.
4. **페르소나 금지 조항** — MUSE_PERSONA가 공개 게시판임을 명시하고 민수 관련
   일체(대화·일정·일기·메모·구매·가족·보안 일화, 익명화 포함)를 금지.

## 4. 프롬프트

- `muse_chance_prompt(today)` — 날짜 앵커 + "WebSearch로 오늘 뉴스 훑거나 weather로 날씨
  보고 견해를 써라. 없으면 패스" (안 쓸 자유 유지)
- `muse_deadline_prompt(today)` — 날짜 앵커 + 뉴스·날씨 중 하나에 대한 견해 필수 1건.
  강제 마감은 유지하되 소재가 세상 이야기로 한정되어 안전해짐.
- PERSONA(대화)에서는 아무말 게시판 규칙 전체 삭제.

## 5. 스케줄·상한 (변경 없음)

랜덤 기회 2회(10~22시) + 23시 마감 체크, `muse_post` 하루 2회 상한 코드 강제 — 그대로.

## 6. 블로그(dev-blog) 동반 변경

- pippi 탭 설명: "삐삐(내 AI)가 매일 뉴스·날씨를 보고 던지는 견해"
- 빈 상태 문구·JS 주석의 "아무말" 표현 정리

## 7. 테스트 (+9 = 79)

- PERSONA에 muse_post·아무말·diary_recent 부재
- MUSE_PERSONA: 공개 인지 + 사적 소재 금지 조항 + 뉴스·날씨 허용 소재
- muse 프롬프트 2종: 날짜 앵커, muse_post 언급, 사적 도구 미참조, 패스 허용
- CHAT_ALLOWED_TOOLS에 muse_post 부재 / MUSE_ALLOWED_TOOLS 3종 고정
- `Brain.ask_fresh`: reset 후 ask 순서 보장

## 8. 배포

`cd /opt/assist && sudo -u assist git pull && sudo systemctl restart assist-bot`
재시작 후 스모크: 대화 정상 → (선택) 다음 muse 기회 글이 뉴스·날씨 견해인지 확인.
