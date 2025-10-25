begin;

-- 0) Rename columns on crosses
do $$
begin
  if exists (select 1 from information_schema.columns  where table_schema='public' and table_name='crosses' and column_name='cross_name') then
    alter table public.crosses rename column cross_name to cross_name_code;
  end if;
  if exists (select 1 from information_schema.columns  where table_schema='public' and table_name='crosses' and column_name='cross_nickname') then
    alter table public.crosses rename column cross_nickname to cross_name_genotype;
  end if;
end$$;

-- 1) Helpers: derive per-fish genotype string, then cross genotype string
create or replace function public.gen_fish_genotype(p_fish_code text)
returns text
language sql
stable
as $$
  select
    coalesce(
      nullif(to_jsonb(f)->>'genotype_label', ''),
      nullif(to_jsonb(f)->>'genotype', ''),
      nullif(to_jsonb(f)->>'genotype_summary', ''),
      nullif(to_jsonb(f)->>'nickname', ''),
      p_fish_code
    )
  from public.fish AS f
  where f.fish_code = p_fish_code
  limit 1
$$;

create or replace function public.gen_cross_genotype(p_mom_code text, p_dad_code text)
returns text
language sql
stable
as $$
  select public.gen_fish_genotype(p_mom_code) || ' × ' || public.gen_fish_genotype(p_dad_code)
$$;

create or replace function public.gen_cross_code_name(p_mom_code text, p_dad_code text)
returns text
language sql
immutable
as $$
  select coalesce(p_mom_code, '') || ' × ' || coalesce(p_dad_code, '')
$$;

-- 2) Backfill both names
update public.crosses
set cross_name_code = public.gen_cross_code_name(mother_code, father_code)
where coalesce(nullif(cross_name_code, ''), '') = '';

update public.crosses
set cross_name_genotype = public.gen_cross_genotype(mother_code, father_code)
where coalesce(nullif(cross_name_genotype, ''), '') = '';

-- 3) Keep them in sync going forward (trigger)
create or replace function public.trg_crosses_set_code_and_genotype()
returns trigger
language plpgsql
as $$
begin
  -- Always set code name from codes AS new.cross_name_code := public.gen_cross_code_name(new.mother_code, new.father_code);

  -- If user didn’t explicitly provide a genotype name, derive it
  if new.cross_name_genotype is null or btrim(new.cross_name_genotype) = '' then
    new.cross_name_genotype := public.gen_cross_genotype(new.mother_code, new.father_code);
  end if;

  return new;
end
$$;

-- drop older name triggers if present
do $$
begin
  if exists (select 1 from pg_trigger  where tgname = 'crosses_set_cross_name' and tgrelid='public.crosses'::regclass) then
    drop trigger crosses_set_cross_name on public.crosses;
  end if;
  if exists (select 1 from pg_trigger  where tgname = 'crosses_set_names' and tgrelid='public.crosses'::regclass) then
    drop trigger crosses_set_names on public.crosses;
  end if;
end$$;

drop trigger if exists crosses_set_nickname_if_null on public.crosses;

create trigger crosses_set_code_and_genotype
before insert or update of mother_code, father_code, cross_name_genotype
on public.crosses
for each row execute function public.trg_crosses_set_code_and_genotype();

-- 4) Enforce non-null for code name (genotype can be edited later)
alter table public.crosses
alter column cross_name_code set not null;

-- 5) Update the overview view to use the new fields (no coalesce with plan)
create or replace view public.v_overview_crosses as
with latest_planned as (
    select distinct on (cp.id)
        cp.id as clutch_id,
        cp.clutch_code,
        cp.status,
        pc.id as planned_id,
        pc.created_at as planned_created_at,
        pc.cross_id,
        pc.mother_tank_id,
        pc.father_tank_id,
        cp.created_at
    from public.clutch_plans AS cp
    left join public.planned_crosses AS pc on cp.id = pc.clutch_id
    order by cp.id asc, pc.created_at desc nulls last
),

counts as (
    select
        clutch_id,
        count(*)::int as planned_count
    from public.planned_crosses  group by clutch_id
)

select
    lp.clutch_code,
    x.cross_name_code as name,       -- fish_code × fish_code
    x.cross_name_genotype as nickname,   -- mom_genotype × dad_genotype
    cp.status::text as status,
    x.mother_code as mom_code,
    x.father_code as dad_code,
    cm.tank_code as mom_code_tank,
    cf.tank_code as dad_code_tank,
    cp.created_at,
    coalesce(ct.planned_count, 0) as planned_count,
    (cm.tank_code is not null and cf.tank_code is not null) as runnable
from public.clutch_plans AS cp
left join latest_planned AS lp on cp.id = lp.clutch_id
left join counts AS ct on cp.id = ct.clutch_id
left join public.crosses AS x on lp.cross_id = x.id
left join public.containers AS cm on lp.mother_tank_id = cm.id
left join public.containers AS cf on lp.father_tank_id = cf.id;

commit;
