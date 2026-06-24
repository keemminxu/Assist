-- assist v2 초기 스키마. 접근은 service role 키로만 (RLS 켜서 anon 차단).

-- owner 컬럼 공통: minsu | haneul | shared (부부 공유 비서)
create table if not exists memories (
  id bigint generated always as identity primary key,
  content text not null,
  category text not null default 'fact',      -- fact | preference | context
  source text not null,                        -- bot | routine
  owner text not null default 'minsu',         -- minsu | haneul | shared
  created_at timestamptz not null default now()
);

-- 채용 48시간 롤링 윈도우 (무한 누적 대신 이틀짜리 중복 제거)
create table if not exists job_seen (
  url_hash text primary key,
  title text,
  site text,                                   -- wanted|jobkorea|saramin|gamejob|remotegamejobs|hitmarker
  seen_at timestamptz not null default now()
);

create table if not exists schedule_notes (
  id bigint generated always as identity primary key,
  note text not null,
  due_at timestamptz,
  category text not null default 'event',    -- event | deadline | birthday | anniversary | campaign
  recurring boolean not null default false,  -- true = 매년 반복 (생일·기념일)
  done boolean not null default false,
  owner text not null default 'minsu',       -- minsu | haneul | shared
  created_at timestamptz not null default now()
);

create table if not exists heartbeat (
  component text primary key,
  last_seen timestamptz not null default now()
);

create table if not exists projects (
  id bigint generated always as identity primary key,
  name text not null unique,
  status text not null default 'active',       -- active | paused | done
  note text,
  owner text not null default 'minsu',         -- minsu | haneul | shared
  created_at timestamptz not null default now()
);

create table if not exists project_tasks (
  id bigint generated always as identity primary key,
  project_id bigint not null references projects(id) on delete cascade,
  task text not null,
  status text not null default 'todo',          -- todo | done
  due_at timestamptz,
  owner text not null default 'minsu',          -- minsu | haneul | shared
  created_at timestamptz not null default now(),
  done_at timestamptz
);

-- 장보기·집안일 공유 리스트 (저녁 브리핑에 미완료 노출)
create table if not exists shared_list (
  id bigint generated always as identity primary key,
  kind text not null default 'grocery',         -- grocery | chore
  item text not null,
  owner text not null default 'shared',         -- minsu | haneul | shared
  done boolean not null default false,
  created_at timestamptz not null default now()
);

-- 공동 가계부 (간단 지출 기록 + 월 합계)
create table if not exists expenses (
  id bigint generated always as identity primary key,
  spent_at timestamptz not null default now(),
  amount integer not null,                       -- 원(KRW), 정수
  category text,                                 -- 식비|카페|마트|교통 등 자유
  memo text,
  owner text not null default 'minsu',           -- minsu | haneul | shared
  created_at timestamptz not null default now()
);

alter table memories enable row level security;
alter table job_seen enable row level security;
alter table schedule_notes enable row level security;
alter table heartbeat enable row level security;
alter table projects enable row level security;
alter table project_tasks enable row level security;
alter table shared_list enable row level security;
alter table expenses enable row level security;
