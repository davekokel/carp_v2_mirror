\set ON_ERROR_STOP on
begin;

-- 0) UUID v4 helper (extension-free)
create or replace function public.fn_uuid_v4()
returns uuid
language sql
immutable
as $$
  select (
    substr(md5(random()::text || clock_timestamp()::text), 1, 8) || '-' ||
    substr(md5(random()::text || clock_timestamp()::text), 1, 4) || '-' ||
    '4' || substr(md5(random()::text || clock_timestamp()::text), 2, 3) || '-' ||
    substr('89ab', floor(random()*4)::int + 1, 1) || substr(md5(random()::text || clock_timestamp()::text), 2, 3) || '-' ||
    substr(md5(random()::text || clock_timestamp()::text), 1, 12)
  )::uuid
$$;

-- 1) fish_pairs (required by tank_pairs + your page logic)
create table if not exists public.fish_pairs (
  id            uuid primary key default public.fn_uuid_v4(),
  mom_fish_id   uuid not null,
  dad_fish_id   uuid not null,
  created_by    text,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  constraint uq_fish_pairs unique (mom_fish_id, dad_fish_id),
  constraint fk_fp_mom foreign key (mom_fish_id) references public.fish(id) on delete restrict,
  constraint fk_fp_dad foreign key (dad_fish_id) references public.fish(id) on delete restrict
);

-- updated_at trigger (idempotent)
create or replace function public.trg_set_updated_at()
returns trigger language plpgsql as $$ begin new.updated_at := now(); return new; end $$;

drop trigger if exists trg_fp_set_updated_at on public.fish_pairs;
create trigger trg_fp_set_updated_at
before update on public.fish_pairs
for each row execute function public.trg_set_updated_at();

create index if not exists idx_fp_mom on public.fish_pairs(mom_fish_id);
create index if not exists idx_fp_dad on public.fish_pairs(dad_fish_id);

-- 2) tank_pair_status enum (ensure exists before table)
do $$
begin
  if not exists (select 1 from pg_type where typname = 'tank_pair_status') then
    create type public.tank_pair_status as enum ('selected','scheduled','crossed','canceled');
  end if;
end$$;

-- 3) tank_pairs (depends on fish_pairs, tanks, clutch_plans)
create table if not exists public.tank_pairs (
  id               uuid primary key default public.fn_uuid_v4(),
  tank_pair_code   text,
  concept_id       uuid,                    -- → clutch_plans.id
  fish_pair_id     uuid,                    -- → fish_pairs.id
  mother_tank_id   uuid not null,           -- → tanks.id
  father_tank_id   uuid not null,           -- → tanks.id
  status           public.tank_pair_status not null default 'selected',
  created_by       text not null,
  note             text,
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now(),
  constraint uq_tank_pairs_concept_mom_dad unique (concept_id, mother_tank_id, father_tank_id),
  constraint fk_tp_concept   foreign key (concept_id)     references public.clutch_plans(id) on delete cascade,
  constraint fk_tp_fishpair  foreign key (fish_pair_id)   references public.fish_pairs(id)  on delete restrict,
  constraint fk_tp_mom_tank  foreign key (mother_tank_id) references public.tanks(id)       on delete restrict,
  constraint fk_tp_dad_tank  foreign key (father_tank_id) references public.tanks(id)       on delete restrict
);

drop trigger if exists trg_tp_set_updated_at on public.tank_pairs;
create trigger trg_tp_set_updated_at
before update on public.tank_pairs
for each row execute function public.trg_set_updated_at();

create index if not exists idx_tp_created_at on public.tank_pairs(created_at desc);
create index if not exists idx_tp_concept    on public.tank_pairs(concept_id);
create index if not exists idx_tp_mom_tank   on public.tank_pairs(mother_tank_id);
create index if not exists idx_tp_dad_tank   on public.tank_pairs(father_tank_id);

-- 4) canonical overview used by page
create or replace view public.v_tank_pairs_overview as
with base as (
  select
    tp.id,
    tp.tank_pair_code,
    tp.concept_id,
    tp.fish_pair_id,
    tp.mother_tank_id,
    tp.father_tank_id,
    tp.status::text   as status,
    tp.created_by,
    tp.created_at
  from public.tank_pairs tp
),
concept as (
  select p.id::uuid as concept_id, coalesce(p.clutch_code, p.id::text) as clutch_code
  from public.clutch_plans p
),
fp as (
  select t.id::uuid as fish_pair_id, t.mom_fish_id, t.dad_fish_id
  from public.fish_pairs t
),
mom_fish as (
  select f.id as mom_fish_id, f.fish_code as mom_fish_code
  from public.fish f
),
dad_fish as (
  select f.id as dad_fish_id, f.fish_code as dad_fish_code
  from public.fish f
),
mtank as (
  select vt.tank_id::uuid as mother_tank_id, vt.tank_code::text as mom_tank_code, vt.status::text as mom_tank_status
  from public.v_tanks_for_fish vt
),
dtank as (
  select vt.tank_id::uuid as father_tank_id, vt.tank_code::text as dad_tank_code, vt.status::text as dad_tank_status
  from public.v_tanks_for_fish vt
)
select
  b.tank_pair_code,
  c.clutch_code,
  b.status,
  b.created_by,
  b.created_at,
  mf.mom_fish_code,
  mt.mom_tank_code,
  df.dad_fish_code,
  dt.dad_tank_code
from base b
left join concept  c   on c.concept_id      = b.concept_id
left join fp       f   on f.fish_pair_id    = b.fish_pair_id
left join mom_fish mf  on mf.mom_fish_id    = f.mom_fish_id
left join dad_fish df  on df.dad_fish_id    = f.dad_fish_id
left join mtank    mt  on mt.mother_tank_id = b.mother_tank_id
left join dtank    dt  on dt.father_tank_id = b.father_tank_id
order by b.created_at desc;

commit;
