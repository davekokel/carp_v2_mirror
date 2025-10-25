begin;

-- 0) Global sequence for allele_number (idempotent)
create sequence if not exists public.transgene_global_allele_seq start 1;

-- 1) Ensure transgene_alleles has the required shape
--    - transgene_base_code (text)
--    - allele_number (int)  -- global across DB
--    - allele_name (text)   -- 'gu' || allele_number
--    - allele_nickname (text) -- string from CSV or defaults to guN
--    Uniques:
--      (transgene_base_code, allele_number)
--      (transgene_base_code, allele_nickname) where nickname not null
do $$
begin
  if not exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='transgene_alleles'
      and column_name='allele_name'
  ) then
    alter table public.transgene_alleles
      add column allele_name text;
  end if;

  if not exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='transgene_alleles'
      and column_name='allele_nickname'
  ) then
    alter table public.transgene_alleles
      add column allele_nickname text;
  end if;

  -- Strong unique by base+number
  if not exists (
    select 1 from pg_indexes
    where schemaname='public' and indexname='ux_transgene_alleles_base_num'
  ) then
    create unique index ux_transgene_alleles_base_num
      on public.transgene_alleles (transgene_base_code, allele_number);
  end if;

  -- Per-base nickname uniqueness (ignore null nicknames)
  if not exists (
    select 1 from pg_indexes
    where schemaname='public' and indexname='ux_transgene_alleles_base_nick'
  ) then
    create unique index ux_transgene_alleles_base_nick
      on public.transgene_alleles (transgene_base_code, allele_nickname)
      where allele_nickname is not null;
  end if;
end $$;

-- 2) Helper: get/create allele for a CSV row
--    Rules implemented:
--      - nickname is always treated as string
--      - if nickname exists for same base => reuse its allele_number
--      - else mint next global number (guN); nickname = CSV string or 'guN' if blank
--    Returns: allele_number, allele_name, allele_nickname (final)
create or replace function public.ensure_allele_from_csv(
  p_base_code text,
  p_allele_nickname text
) returns table(allele_number int, allele_name text, allele_nickname text)
language plpgsql
as $$
declare
  v_nick text := nullif(p_allele_nickname, '');
  v_num  int;
  v_name text;
begin
  -- 2.a) If nickname present, try reuse per base
  if v_nick is not null then
    select ta.allele_number, ta.allele_name, ta.allele_nickname
      into allele_number, allele_name, allele_nickname
    from public.transgene_alleles ta
    where ta.transgene_base_code = p_base_code
      and ta.allele_nickname = v_nick
    limit 1;

    if found then
      return next;
      return;
    end if;
  end if;

  -- 2.b) Mint a new global allele number
  v_num := nextval('public.transgene_global_allele_seq')::int;
  v_name := 'gu' || v_num::text;

  -- 2.c) Insert canonical allele row for this base/number
  insert into public.transgene_alleles (transgene_base_code, allele_number, allele_name, allele_nickname)
  values (p_base_code, v_num, v_name, coalesce(v_nick, v_name))
  on conflict (transgene_base_code, allele_number) do nothing;

  allele_number  := v_num;
  allele_name    := v_name;
  allele_nickname:= coalesce(v_nick, v_name);
  return next;
end
$$;

-- 3) Upsert linker for fish <- allele (CSV path)
--    - Ensures allele row exists via ensure_allele_from_csv
--    - Upserts into fish_transgene_alleles by (fish_id, base_code)
create or replace function public.upsert_fish_allele_from_csv(
  p_fish_id uuid,
  p_base_code text,
  p_allele_nickname text
) returns table(fish_id uuid, transgene_base_code text, allele_number int)
language plpgsql
as $$
declare
  v_num  int;
  v_name text;
  v_nick text;
begin
  -- resolve/mint allele per the rules
  select ea.allele_number, ea.allele_name, ea.allele_nickname
    into v_num, v_name, v_nick
  from public.ensure_allele_from_csv(p_base_code, p_allele_nickname) ea;

  -- link to fish (idempotent)
  insert into public.fish_transgene_alleles (fish_id, transgene_base_code, allele_number)
  values (p_fish_id, p_base_code, v_num)
  on conflict (fish_id, transgene_base_code)
  do update set allele_number = excluded.allele_number;

  fish_id := p_fish_id;
  transgene_base_code := p_base_code;
  allele_number := v_num;
  return next;
end
$$;

-- 4) v_fish_standard_clean with the requested columns & rollups
create or replace view public.v_fish_standard_clean as
with per_allele as (
  select
    f.fish_code,
    f.name,
    f.nickname,
    f.genetic_background,
    coalesce(f.line_building_stage,'') as line_building_stage,
    f.date_birth,
    f.created_at,
    f.created_by,
    fta.transgene_base_code,
    ta.allele_number,
    ta.allele_name,
    ta.allele_nickname,
    ('Tg('||fta.transgene_base_code||')'||coalesce(ta.allele_nickname,'')) as transgene_pretty_nickname,
    ('Tg('||fta.transgene_base_code||')'||coalesce(ta.allele_name,''))     as transgene_pretty_name
  from public.fish f
  left join public.fish_transgene_alleles fta
    on fta.fish_id = f.id
  left join public.transgene_alleles ta
    on ta.transgene_base_code = fta.transgene_base_code
   and ta.allele_number       = fta.allele_number
),
geno_roll as (
  select
    fish_code,
    string_agg(distinct transgene_pretty_name, '; ' order by transgene_pretty_name) as genotype
  from per_allele
  group by fish_code
)
select
  p.fish_code,
  p.name,
  p.nickname,
  p.genetic_background,
  p.line_building_stage,
  p.date_birth,
  p.created_at,
  p.created_by,
  p.transgene_base_code,
  p.allele_number,
  p.allele_name,
  p.allele_nickname,
  p.transgene_pretty_nickname,
  p.transgene_pretty_name,
  g.genotype
from per_allele p
left join geno_roll g using (fish_code)
order by p.created_at desc nulls last, p.fish_code;

commit;
