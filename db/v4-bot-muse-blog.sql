-- blog Supabase (mnatdbpscbvhhsxstvaq) 에 적용
create table if not exists bot_muse (
  id bigint generated always as identity primary key,
  content text not null,
  created_at timestamptz not null default now()
);
alter table bot_muse enable row level security;  -- service key로만 접근
