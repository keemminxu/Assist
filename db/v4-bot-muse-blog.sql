-- blog Supabase (mnatdbpscbvhhsxstvaq) 에 적용
create table if not exists bot_muse (
  id bigint generated always as identity primary key,
  content text not null,
  created_at timestamptz not null default now()
);
alter table bot_muse enable row level security;

-- 쓰기는 service key(봇)로만. anon은 SELECT 하나뿐 — 블로그 프론트(pippi.js)가 읽는다.
-- 이 내용이 muse 프롬프트에 재주입되므로(recent_posts) anon 쓰기 정책을 절대 추가하지 마라.
-- (운영 DB 실제 정책과 일치 확인: 2026-07-27, pg_policies 덤프)
create policy "bot_muse anon read" on bot_muse for select to anon using (true);
