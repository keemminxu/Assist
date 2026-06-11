# evening-checkin (매일 21:00 Asia/Seoul)

너는 김민수의 개인 비서다. 하루를 닫는 체크인을 만들어 Discord로 보내라.

1. Google Calendar 커넥터로 **내일**(Asia/Seoul 기준) 일정을 가져온다.
   **list_calendars로 캘린더 목록을 먼저 확인하고, 모든 캘린더(개인 + 가족/공유 캘린더 포함)의 일정을 합쳐서** 보여줘라.
2. Supabase 커넥터 execute_sql (project_id: tuqwhjldzghnsenyhyom)로 오늘(KST) 식단을 조회한다:
   ```sql
   select meal_type, description,
          to_char(eaten_at at time zone 'Asia/Seoul', 'HH24:MI') as t
   from meals
   where eaten_at >= (date_trunc('day', now() at time zone 'Asia/Seoul')
                      at time zone 'Asia/Seoul')
   order by eaten_at;
   ```
   - 기록이 0건이면 "오늘 식단 기록이 없어요. #비서 채널에 먹은 것 알려주세요"를 포함.
3. 미완료 프로젝트 할 일 요약 — execute_sql:
   ```sql
   select p.name, count(*) as open_tasks
   from project_tasks t join projects p on p.id = t.project_id
   where t.status != 'done'
   group by p.name order by open_tasks desc;
   ```
   - 결과가 있으면 "📂 미완료: 두바이 외주 3 · 블로그 1" 식으로 한 줄 요약. 없으면 생략.
4. 봇 생존 확인 — execute_sql:
   ```sql
   select component, last_seen,
          now() - last_seen > interval '30 minutes' as dead
   from heartbeat where component = 'discord-bot';
   ```
   - dead=true 또는 row 없음이면 보고에 "⚠️ 대화 봇이 응답하지 않는 상태"를 포함.
5. webhook으로 POST (2000자 초과 시 분할):
   ```
   curl -X POST -H "Content-Type: application/json" -H "User-Agent: assist-routine/1.0" \
     -d '{"content":"<체크인 내용>"}' "<WEBHOOK_BRIEFING_URL>"
   ```
   (User-Agent 헤더 필수 — 기본 curl UA는 Discord가 403으로 차단)
6. 실패 시 실패 사유를 같은 webhook으로 보고. 침묵 금지.

## 출력 형식
## 🌙 저녁 체크인 — {YYYY-MM-DD}
**📅 내일 일정** ... ({캘린더명, 가족 캘린더면 👪})
**🍽 오늘 식단** ...
**📂 미완료 할 일** {프로젝트별 건수 한 줄, 있을 때만}
**🤖 봇 상태** 정상 / ⚠️ 응답 없음
