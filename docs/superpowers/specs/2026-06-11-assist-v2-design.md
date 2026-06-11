# assist v2 — 24시간 개인 비서 설계

날짜: 2026-06-11
상태: 승인됨 (A안 + C안 병행)

## 1. 목표

Discord로 소통하는 24시간 개인 비서. 핵심 기능:

- 메일 요약 (Gmail)
- 일정 확인·세부 스케줄 관리 (Google Calendar)
- 채용공고 수집·요약·보고 (언리얼/Unreal 키워드 — 원티드, 게임잡, 사람인, 잡코리아)
- 식단 기록·관리 (대화 기반 입력)
- 알게 된 사실을 DB에 누적해 "하나의 기억"을 가진 비서

사용자는 언리얼 엔진 개발자. 기존 v1 프로젝트(OpenClaw 프록시 + Oracle 배포)는 폐기하고 새로 시작하되 `oci-retry/`만 재활용한다.

## 2. 확정된 제약·결정

| 항목 | 결정 |
|---|---|
| Claude 요금제 | Max 구독 — 비서의 두뇌는 구독 기반 (API 추가 과금 없음) |
| 인프라 예산 | 무료 우선, 필요 시 월 $5까지 허용 |
| 소통 방식 | 양방향 — 정기 보고(push) + 자유 대화(채팅) 둘 다 |
| 접근 방식 | A안(하이브리드) + C안(Oracle A1 병행 확보) |
| Cowork | 사용 안 함 — 데스크톱 상주 필요라 24시간 요구사항과 충돌 |
| v1 실패 원인 | ① OCI 무료 티어 capacity 확보 실패 ② 프록시 경유 429 ③ DB 부재 — 셋 다 이번 설계에서 구조적으로 제거 |

## 3. 전체 아키텍처

```
[Anthropic 클라우드 — 서버 0대]            [GCP e2-micro (무료) → Oracle A1 (잡히면 이전)]
 스케줄 에이전트 (routines)                  Discord 대화 봇 (Python, 얇은 릴레이)
  ├─ 아침 브리핑 (메일+일정)                  ├─ 메시지 수신 → claude -p 헤드리스 호출
  ├─ 채용공고 스캔 (언리얼)                   ├─ 직렬 큐 + 429 백오프 + 모델 다운시프트
  └─ 저녁 체크인 (내일일정+식단)              └─ systemd 상시 구동, Max 구독 토큰 인증
       │                                          │
       └──── Discord Webhook ───→ [Discord 채널] ←─ Gateway ─┘

              [Supabase 무료 Postgres] ← 양쪽이 같은 DB를 공유 = "하나의 기억"
              [Google Drive 5TB]      ← 대용량 파일·백업 전용
```

핵심 원칙: **두뇌는 두 곳(routines + 봇), 기억은 한 곳(Supabase)**. 대화로 입력한
사실을 routines가 알고, routines가 수집한 것을 대화에서 물어볼 수 있다.

## 4. 컴포넌트

### 4.1 클라우드 routines (서버리스 정기 작업)

Claude Code 스케줄 에이전트(`/schedule`)로 등록. Anthropic 인프라에서 크론 실행,
Max 구독 한도를 소모한다 (일 3개 루틴 수준은 한도에 무리 없음).

| 루틴 | 시각 (KST) | 동작 | 출력 |
|---|---|---|---|
| morning-briefing | 매일 07:30 | Gmail 커넥터로 지난 24h 메일 요약 + Google Calendar 오늘 일정 정리 | #브리핑 webhook |
| job-scan | 매일 09:00 | 4개 채용 사이트에서 "언리얼/Unreal" 신규 공고 수집 → `job_postings`로 dedup → 새 공고만 요약 | #채용 webhook |
| evening-checkin | 매일 21:00 | 내일 일정 미리보기 + 오늘 `meals` 기록 요약, 누락 시 리마인드 + 봇 heartbeat 확인 | #브리핑 webhook |

공통 규칙:

- 출력은 Discord **webhook URL에 POST** (봇 토큰 불필요, 수신 측 무료)
- 실패 시 침묵 금지 — "오늘 OO 실패: 사유"를 같은 채널로 전송
- 채용 수집은 사이트별 3단 fallback: 직접 fetch → 검색 경유 → "수집 실패" 명시 보고

### 4.2 Discord 대화 봇 (유일한 상시 프로세스)

- discord.py gateway 연결. 메시지 수신 → `claude -p` 헤드리스 호출 → 응답 전송
- 봇 자체는 200줄 미만의 얇은 릴레이. 지능(웹검색, Supabase 읽기/쓰기, 일정 조작,
  식단 기록)은 Claude Code가 도구로 수행
- 인증: `claude setup-token` 장기 토큰 (Max 구독)
- 429 대응: 채널별 직렬 큐 + 지수 백오프, 한도 임박 시 Haiku 다운시프트
- 세션 연속성: 채널별 `--resume` 세션 유지, 핵심 사실은 `memories` 테이블에 영속화
- 생존 신호: 5분마다 `heartbeat` 테이블 갱신 → evening-checkin이 확인
  (last_seen이 30분 이상 과거면 사망 판정), 죽어 있으면 Discord로 알림
- 배포: systemd 서비스, 자동 재시작

### 4.3 DB — Supabase 무료 티어 (MCP 커넥터 이미 연결됨)

시작 테이블 5개:

| 테이블 | 용도 |
|---|---|
| `memories` | 비서가 알게 된 사실·선호 (대화/루틴 양쪽에서 기록) |
| `meals` | 식단 기록 (시각, 끼니, 내용, 메모) |
| `job_postings` | 공고 URL 해시로 dedup, 제목/회사/요약/상태(신규·보고됨·관심) |
| `schedule_notes` | 캘린더에 없는 일정 보조 메모 |
| `heartbeat` | 봇 생존 신호 (component, last_seen) |

- 무료 티어 "7일 미사용 시 일시정지"는 매일 routines가 읽고 써서 자연 해소
- Google Drive 5TB는 대용량 파일(첨부 보관, DB 백업 덤프) 전용. 정형 데이터는 넣지 않음

### 4.4 Oracle A1 병행 트랙 (C안)

- 기존 `oci-retry/retry-launch.sh` 재활용 (OCID 기입 완료 상태, AP-TOKYO-1, 2 OCPU/12GB)
- **PAYG(Pay-As-You-Go) 전환 권장**: Always Free 한도는 유지되면서 capacity 거절이
  대부분 해소됨. 전환 시 과금 한도 알림(budget alert) 설정 필수
- capacity 확보 시 이전 절차: `git pull` → `.env` 복사 → systemd 등록 → GCP 봇 중지
  → 24h 병행 관찰 → GCP 인스턴스 삭제. 봇이 얇아서 이전은 30분 거리

## 5. Discord 채널 구성

| 채널 | 용도 |
|---|---|
| #비서 | 자유 대화 (봇이 모든 메시지에 응답) |
| #브리핑 | 아침 브리핑, 저녁 체크인 (webhook 전용) |
| #채용 | 신규 언리얼 공고 알림 (webhook 전용) |

## 6. 에러 처리

| 실패 지점 | 대응 |
|---|---|
| routine 실행 실패 | webhook으로 실패 사유 보고 (침묵 실패 금지) |
| 채용 사이트 봇 차단 | 사이트별 3단 fallback, 최종 실패도 명시 보고 |
| 429 (구독 한도) | 봇: 직렬 큐 + 지수 백오프 + Haiku 다운시프트. 한도 도달 시 사용자에게 안내 후 대기 |
| 봇 프로세스 다운 | systemd 자동 재시작 + heartbeat 기반 사망 알림 |
| Supabase 접근 실패 | 봇은 대화 기능 유지(기억 기능만 일시 저하), 루틴은 실패 보고 |

## 7. 검증 계획 (위험 큰 순서)

1. Discord webhook 전송 확인 — 5분짜리 기반 검증
2. **채용 사이트 4곳 수집 가능성 사전 검증** — 최대 리스크. 막히는 사이트는
   검색 경유 fallback을 설계 단계에서 확정
3. **morning-briefing 루틴 1개 실등록** — 클라우드 실행 환경에서 Gmail/Calendar
   커넥터가 실제로 붙는지 확인 (두 번째 리스크. 안 붙으면 해당 기능을 봇 쪽으로 이동)
4. 봇 로컬 개발·테스트 → GCP e2-micro 배포 → 실사용

## 8. 비범위 (YAGNI)

- Slack 연동, 음성 인터페이스, 웹 대시보드
- 다중 사용자 지원 (사용자 1인 전용)
- LinkedIn 크롤링 (차단 강함 — 필요해지면 이메일 알림 요약으로 별도 검토)
- v1 코드 재활용 (`oci-retry/` 제외 전부 폐기)
