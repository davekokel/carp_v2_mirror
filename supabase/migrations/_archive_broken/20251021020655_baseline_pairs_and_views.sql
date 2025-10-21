\set ON_ERROR_STOP on
begin;

-- UUID v4 generator (extension-free, deterministic shape)
create or replace function public.fn_uuid_v4()
returns uuid language sql immutable as $$
  select (
    lpad(to_hex((random()*4294967295)::bigint & x'ffffffff'::bigint),8,'0') || '-' ||
    lpad(to_hex((random()*65535)::bigint     & x'ffff'::bigint),4,'0')      || '-' ||
    lpad(to_hex(((random()*65535)::bigint   & x'0fff'::bigint) | x'4000'::bigint),4,'0') || '-' ||
    lpad(to_hex(((random()*65535)::bigint   & x'3fff'::bigint) | x'8000'::bigint),4,'0') || '-' ||
    lpad(to_hex((random()*281474976710655)::numeric(20,0) & x'ffffffffffff'::numeric(20,0)),12,'0')
  )::uuid
$$;

-- Enum first (so table create cannot fail)
do $$
begin
  if not exists (select 1 from pg_type where typname = 'tank_pair_status') then
    create type public.tank_pair_status as enum ('selected','scheduled','crossed','canceled');
  end if;
end$$;

-- tank_pairs table (idempotent; assumes referenced tables exist)
create table if not exists public.tank_pairs (
  id               uuid primary key default public.fn_uuid_v4(),
  tank_pair_code   text,
  concept_id       uuid,                    -- → public.clutch_plans(id)
  fish_pair_id     uuid,                    -- → public.fish_pairs(id)
  mother_tank_id   uuid not null,           -- → public.tanks(id)
  father_tank_id   uuid not null,           -- → public.tanks(id)
  status           public.tank_pair_status not null default 'selected',
  created_by       text not null,
  note             text,
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now(),
  constraint uq_tank_pairs_concept_mom_dad unique (concept_id, mother_tank_id, father_tank_id),
  constraint fk_tank_pairs_concept   foreign key (concept_id)     references public.clutch_plans(id) on delete cascade,
  constraint fk_tank_pairs_fishpair  foreign key (fish_pair_id)   references public.fish_pairs(id)  on delete restrict,
  constraint fk_tank_pairs_mom_tank  foreign key (mother_tank_id) references public.tanks(id)       on delete restrict,
  constraint fk_tank_pairs_dad_tank  foreign key (father_tank_id) references public.tanks(id)       on delete restrict
);

-- updated_at trigger
create or replace function public.trg_set_updated_at()
returns trigger language plpgsql as $$
begin new.updated_at := now(); return new; end $$;

drop trigger if exists trg_tp_set_updated_at on public.tank_pairs;
create trigger trg_tp_set_updated_at
before update on public.tank_pairs
for each row execute function public.trg_set_updated_at();

-- helpful indexes
create index if not exists idx_tp_created_at on public.tank_pairs(created_at desc);
create index if not exists idx_tp_concept    on public.tank_pairs(concept_id);
create index if not exists idx_tp_mom_tank   on public.tank_pairs(mother_tank_id);
create index if not exists idx_tp_dad_tank   on public.tank_pairs(father_tank_id);

-- Rollup: Tg(base)guN per fish
create or replace view public.v_fish_genotype_rollup as
with a as (
  select
    f.fish_code,
    'Tg(' || fta.transgene_base_code || ')' || coalesce(ta.allele_name,'') as transgene_pretty
  from public.fish f
  left join public.fish_transgene_alleles fta on fta.fish_id = f.id
  left join public.transgene_alleles ta
         on ta.transgene_base_code = fta.transgene_base_code
        and ta.allele_number       = fta.allele_number
)
select fish_code,
       coalesce(string_agg(transgene_pretty, '; ' order by transgene_pretty), '') as genotype
from a
group by fish_code;

-- Enriched clutches view (your desired columns)
create or replace view public.v_clutches_overview as
with tx_counts as (
  select clutch_id, count(*)::int as n_treatments
  from public.clutch_plan_treatments
  group by clutch_id
),
mom_core as (
  select f.fish_code as mom_code, f.genetic_background as mom_background, f.date_birth as mom_birth
  from public.fish f
),
dad_core as (
  select f.fish_code as dad_code, f.genetic_background as dad_background, f.date_birth as dad_birth
  from public.fish f
),
mom_roll as (
  select fish_code as mom_code, genotype as mom_genotype_rollup
  from public.v_fish_genotype_rollup
),
dad_roll as (
  select fish_code as dad_code, genotype as dad_genotype_rollup
  from public.v_fish_genotype_rollup
)
select
  coalesce(p.clutch_code, p.id::text)  as clutch_code,
  coalesce(p.planned_name,'')          as name,
  coalesce(p.planned_nickname,'')      as nickname,
  p.mom_code                           as mom_code,
  coalesce(mo.mom_background,'')       as mom_background,
  coalesce(mr.mom_genotype_rollup,'')  as mom_genotype_rollup,
  0::int                               as mom_n_living_tanks,
  mo.mom_birth                         as mom_birth,
  p.dad_code                           as dad_code,
  coalesce(dcore.dad_background,'')    as dad_background,
  coalesce(dr.dad_genotype_rollup,'')  as dad_genotype_rollup,
  0::int                               as dad_n_living_tanks,
  dcore.dad_birth                      as dad_birth,
  coalesce(t.n_treatments,0)           as n_treatments,
  p.created_by                         as created_by,
  p.created_at                         as created_at
from public.clutch_plans p
left join tx_counts t   on t.clutch_id      = p.id
left join mom_core  mo  on mo.mom_code      = p.mom_code
left join dad_core  dcore on dcore.dad_code = p.dad_code
left join mom_roll  mr  on mr.mom_code      = p.mom_code
left join dad_roll  dr  on dr.dad_code      = p.dad_code
order by p.created_at desc;

-- Canonical tank pair overview (exact columns the page reads)
create or replace view public.v_tank_pairs_overview as
with base as (
  select
    tp.id,
    tp.tank_pair_code,
    tp.concept_id,
    tp.fish_pair_id,
    tp.mother_tank_id,
    tp.father_tank_id,
    tp.status::text         as status,
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
