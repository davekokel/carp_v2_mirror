BEGIN;

do $$
begin
  if exists (select 1 from information_schema.columns where table_schema='public' and table_name='crosses' and column_name='cross_name') then
    alter table public.crosses rename column cross_name to cross_name_code;
  end if;
  if exists (select 1 from information_schema.columns where table_schema='public' and table_name='crosses' and column_name='cross_nickname') then
    alter table public.crosses rename column cross_nickname to cross_name_genotype;
  end if;
end$$;

create table if not exists public.cross_parent_aliases (
  parent_code text primary key,
  alias text not null
);

create or replace function public.gen_fish_genotype(p_fish_code text)
returns text
language sql
stable
as $$
  select coalesce(
    (select alias from public.cross_parent_aliases where parent_code=p_fish_code),
    nullif(to_jsonb(f)->>'genotype_label',''),
    nullif(to_jsonb(f)->>'genotype',''),
    nullif(to_jsonb(f)->>'genotype_summary',''),
    nullif(to_jsonb(f)->>'nickname',''),
    p_fish_code
  )
  from public.fish f
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
  select coalesce(p_mom_code,'') || ' × ' || coalesce(p_dad_code,'')
$$;

update public.crosses
set cross_name_code = public.gen_cross_code_name(mother_code, father_code)
where coalesce(nullif(cross_name_code,''),'') = '';

update public.crosses
set cross_name_genotype = public.gen_cross_genotype(mother_code, father_code)
where coalesce(nullif(cross_name_genotype,''),'') = '';

create or replace function public.trg_crosses_set_code_and_genotype()
returns trigger
language plpgsql
as $$
begin
  new.cross_name_code := public.gen_cross_code_name(new.mother_code, new.father_code);
  if new.cross_name_genotype is null or btrim(new.cross_name_genotype) = '' then
    new.cross_name_genotype := public.gen_cross_genotype(new.mother_code, new.father_code);
  end if;
  return new;
end
$$;

do $$
begin
  if exists (select 1 from pg_trigger where tgname='crosses_set_cross_name' and tgrelid='public.crosses'::regclass) then
    drop trigger crosses_set_cross_name on public.crosses;
  end if;
  if exists (select 1 from pg_trigger where tgname='crosses_set_names' and tgrelid='public.crosses'::regclass) then
    drop trigger crosses_set_names on public.crosses;
  end if;
  if exists (select 1 from pg_trigger where tgname='crosses_set_nickname_if_null' and tgrelid='public.crosses'::regclass) then
    drop trigger crosses_set_nickname_if_null on public.crosses;
  end if;
end$$;

drop trigger if exists crosses_set_code_and_genotype on public.crosses;

create trigger crosses_set_code_and_genotype
before insert or update of mother_code, father_code, cross_name_genotype
on public.crosses
for each row
execute function public.trg_crosses_set_code_and_genotype();

alter table public.crosses
  alter column cross_name_code set not null;

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
  from public.clutch_plans cp
  left join public.planned_crosses pc on pc.clutch_id = cp.id
  order by cp.id, pc.created_at desc nulls last
),
counts as (
  select clutch_id, count(*)::int as planned_count
  from public.planned_crosses
  group by clutch_id
)
select
  lp.clutch_code,
  x.cross_name_code     as name,
  x.cross_name_genotype as nickname,
  cp.status::text       as status,
  coalesce(ct.planned_count,0) as planned_count,
  x.mother_code         as mom_code,
  x.father_code         as dad_code,
  cm.tank_code          as mom_code_tank,
  cf.tank_code          as dad_code_tank,
  cp.created_at,
  (cm.tank_code is not null and cf.tank_code is not null) as runnable
from public.clutch_plans cp
left join latest_planned lp on lp.clutch_id = cp.id
left join counts ct on ct.clutch_id = cp.id
left join public.crosses x on x.id = lp.cross_id
left join public.containers cm on cm.id = lp.mother_tank_id
left join public.containers cf on cf.id = lp.father_tank_id;

COMMIT;
