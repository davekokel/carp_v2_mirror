BEGIN;

create sequence if not exists public.transgene_allele_number_seq start 1;

create table if not exists public.transgene_alleles (
  transgene_base_code text not null,
  allele_number int not null,
  allele_name text not null,
  allele_nickname text,
  created_at timestamptz not null default now(),
  primary key (transgene_base_code, allele_number)
);

create unique index if not exists uq_transgene_alleles_global_number on public.transgene_alleles(allele_number);
create unique index if not exists uq_transgene_alleles_nickname_per_base on public.transgene_alleles(transgene_base_code, allele_nickname) where allele_nickname is not null;

create or replace function public.upsert_transgene_allele(p_base text, p_nickname_in text)
returns table(transgene_base_code text, allele_number int, allele_name text, allele_nickname text)
language plpgsql
as $$
declare
  v_nickname text := nullif(trim(p_nickname_in), '');
  v_num int;
  v_name text;
begin
  if v_nickname is not null then
    select ta.transgene_base_code, ta.allele_number, ta.allele_name, ta.allele_nickname
      into transgene_base_code, allele_number, allele_name, allele_nickname
    from public.transgene_alleles ta
    where ta.transgene_base_code = p_base
      and ta.allele_nickname = v_nickname
    limit 1;
    if found then
      return next;
      return;
    end if;
  end if;

  loop
    begin
      v_num := nextval('public.transgene_allele_number_seq')::int;
      v_name := 'gu' || v_num::text;
      insert into public.transgene_alleles(transgene_base_code, allele_number, allele_name, allele_nickname)
      values (p_base, v_num, v_name, coalesce(v_nickname, v_name))
      returning transgene_base_code, allele_number, allele_name, allele_nickname
      into transgene_base_code, allele_number, allele_name, allele_nickname;
      return next;
      return;
    exception when unique_violation then
      continue;
    end;
  end loop;
end
$$;

create or replace function public.link_fish_to_transgene_allele(p_fish_uuid uuid, p_base text, p_nickname text)
returns table(fish_uuid uuid, transgene_base_code text, allele_number int)
language plpgsql
as $$
declare r record;
begin
  select * into r from public.upsert_transgene_allele(p_base, p_nickname);
  insert into public.fish_transgene_alleles(fish_uuid, transgene_base_code, allele_number)
  values (p_fish_uuid, r.transgene_base_code, r.allele_number)
  on conflict do nothing;
  fish_uuid := p_fish_uuid;
  transgene_base_code := r.transgene_base_code;
  allele_number := r.allele_number;
  return next;
end
$$;

do $$
begin
  if not exists (select 1 from pg_type where typname='tank_status') then
    create type public.tank_status as enum ('active','to_kill','retired');
  end if;
end$$;

do $$
begin
  if not exists (select 1 from information_schema.columns where table_schema='public' and table_name='tanks' and column_name='status') then
    alter table public.tanks add column status public.tank_status;
  end if;
end$$;

update public.tanks set status='active' where status is null;
alter table public.tanks alter column status set not null;
alter table public.tanks alter column status set default 'active';

do $$
begin
  if not exists (select 1 from information_schema.columns where table_schema='public' and table_name='tanks' and column_name='tank_code') then
    alter table public.tanks add column tank_code text;
  end if;
end$$;

create unique index if not exists uq_tanks_tank_code on public.tanks(tank_code) where tank_code is not null;

create or replace function public.next_tank_num_for_fish(p_fish_code text)
returns int
language sql
as $$
  select coalesce(max((regexp_replace(t.tank_code, '.*#', '')::int)),0)+1
  from public.tanks t
  where t.tank_code like ('TANK('||p_fish_code||')#%')
$$;

create or replace function public.make_tank_code_for_fish(p_fish_code text)
returns text
language plpgsql
as $$
declare n int;
begin
  n := public.next_tank_num_for_fish(p_fish_code);
  return 'TANK('||p_fish_code||')#'||n::text;
end
$$;

create or replace function public.fish_auto_tank()
returns trigger
language plpgsql
security definer
set search_path=public
as $$
declare v_code text;
begin
  v_code := public.make_tank_code_for_fish(new.fish_code);
  insert into public.tanks(status, tank_code) values ('active', v_code);
  return new;
end
$$;

alter function public.fish_auto_tank() owner to current_user;

drop trigger if exists trg_fish_auto_tank on public.fish;
create trigger trg_fish_auto_tank after insert on public.fish for each row execute function public.fish_auto_tank();

do $$
begin
  if not exists (select 1 from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname='public' and c.relname='tanks' and c.relrowsecurity) then
    alter table public.tanks enable row level security;
  end if;
  if not exists (select 1 from pg_policies where schemaname='public' and tablename='tanks' and policyname='tanks_select_all') then
    create policy tanks_select_all on public.tanks for select using (true);
  end if;
  if not exists (select 1 from pg_policies where schemaname='public' and tablename='tanks' and policyname='tanks_insert_all') then
    create policy tanks_insert_all on public.tanks for insert with check (true);
  end if;
end$$;

drop view if exists public.v_fish_rich;
create view public.v_fish_rich as
with alleles as (
  select
    fta.fish_uuid,
    ta.transgene_base_code,
    ta.allele_number,
    ('gu'||ta.allele_number::text) as allele_name,
    ta.allele_nickname,
    ('Tg('||ta.transgene_base_code||')'||coalesce(ta.allele_nickname,'gu'||ta.allele_number::text)) as transgene_pretty_nickname,
    ('Tg('||ta.transgene_base_code||')'||'gu'||ta.allele_number::text) as transgene_pretty_name
  from public.fish_transgene_alleles fta
  join public.transgene_alleles ta
    on ta.transgene_base_code = fta.transgene_base_code
   and ta.allele_number       = fta.allele_number
),
allele_rollups as (
  select
    fish_uuid,
    array_agg(allele_number order by transgene_pretty_name) as allele_numbers,
    array_agg(allele_name order by transgene_pretty_name) as allele_names,
    array_agg(allele_nickname order by transgene_pretty_name) as allele_nicknames,
    string_agg(transgene_pretty_nickname,'; ' order by transgene_pretty_nickname) as genotype_rollup_by_nickname,
    string_agg(transgene_pretty_name,'; ' order by transgene_pretty_name) as genotype_rollup_by_name
  from alleles
  group by fish_uuid
),
first_allele as (
  select distinct on (fish_uuid)
    fish_uuid, transgene_base_code, allele_number, allele_name, allele_nickname, transgene_pretty_nickname, transgene_pretty_name
  from alleles
  order by fish_uuid, transgene_pretty_name
)
select
  f.fish_uuid,
  f.fish_code,
  null::text as fish_name,
  null::text as fish_nickname,
  f.genetic_background,
  f.line_building_stage,
  f.date_birth,
  coalesce((select count(*) from public.tanks t where t.status='active' and t.tank_code like ('TANK('||f.fish_code||')#%')),0)::int as n_active_tanks,
  coalesce(fa.allele_nickname,'') as allele_nickname,
  fa.allele_number,
  coalesce(fa.allele_name,'') as allele_name,
  coalesce(fa.transgene_pretty_nickname,'') as transgene_pretty_nickname,
  coalesce(fa.transgene_pretty_name,'') as transgene_pretty_name,
  coalesce(ar.allele_numbers,array[]::int[]) as allele_numbers,
  coalesce(ar.allele_names,array[]::text[]) as allele_names,
  coalesce(ar.allele_nicknames,array[]::text[]) as allele_nicknames,
  coalesce(ar.genotype_rollup_by_nickname,'') as genotype_rollup_by_nickname,
  coalesce(ar.genotype_rollup_by_name,'') as genotype_rollup_by_name,
  (coalesce(array_length(ar.allele_numbers,1),0)=0) as is_wildtype,
  case when coalesce(array_length(ar.allele_numbers,1),0)=0 then 'WT('||coalesce(f.genetic_background,'')||')' else coalesce(ar.genotype_rollup_by_name,'') end as genotype_pretty,
  f.created_at,
  f.updated_at
from public.fish f
left join first_allele fa on fa.fish_uuid = f.fish_uuid
left join allele_rollups ar on ar.fish_uuid = f.fish_uuid;

insert into public.tanks(status, tank_code)
select 'active', 'TANK('||f.fish_code||')#1'
from public.fish f
left join lateral (
  select 1 from public.tanks t
  where t.tank_code like ('TANK('||f.fish_code||')#%')
  limit 1
) has on true
where has is null;

COMMIT;
