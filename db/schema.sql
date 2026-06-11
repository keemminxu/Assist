-- assist v2 초기 스키마. 접근은 service role 키로만 (RLS 켜서 anon 차단).

create table if not exists memories (
  id bigint generated always as identity primary key,
  content text not null,
  category text not null default 'fact',      -- fact | preference | context
  source text not null,                        -- bot | routine
  created_at timestamptz not null default now()
);

create table if not exists meals (
  id bigint generated always as identity primary key,
  eaten_at timestamptz not null default now(),
  meal_type text not null default 'snack',     -- breakfast | lunch | dinner | snack
  description text not null,
  note text,
  created_at timestamptz not null default now()
);

create table if not exists job_postings (
  id bigint generated always as identity primary key,
  url_hash text not null unique,
  url text not null,
  title text not null,
  company text,
  site text not null,                          -- wanted | gamejob | saramin | jobkorea
  summary text,
  status text not null default 'new',          -- new | reported | interested | dismissed
  found_at timestamptz not null default now()
);

create table if not exists schedule_notes (
  id bigint generated always as identity primary key,
  note text not null,
  due_at timestamptz,
  done boolean not null default false,
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
  created_at timestamptz not null default now()
);

create table if not exists project_tasks (
  id bigint generated always as identity primary key,
  project_id bigint not null references projects(id) on delete cascade,
  task text not null,
  status text not null default 'todo',          -- todo | done
  due_at timestamptz,
  created_at timestamptz not null default now(),
  done_at timestamptz
);

alter table memories enable row level security;
alter table meals enable row level security;
alter table job_postings enable row level security;
alter table schedule_notes enable row level security;
alter table heartbeat enable row level security;
alter table projects enable row level security;
alter table project_tasks enable row level security;
