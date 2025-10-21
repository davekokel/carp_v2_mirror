begin;

-- 1) Alias table (already created earlier; keep here for idempotency)
create table if not exists public.cross_parent_aliases (
    parent_code text primary key,
    alias text not null
);

-- 2) Display rule for a single allele
create or replace function public._allele_display(p_base text, p_num int, p_nick text)
returns text
language sql
immutable
as $$
  select coalesce(nullif(p_nick, ''), 'Tg(' || p_base || ')' || p_num::text)
$$;

-- 3) Build a fish genotype from (a) alias override, else (b) transgene alleles, else (c) fish_code
create or replace function public.gen_fish_genotype(p_fish_code text)
returns text
language sql
stable
as $$
  with alias as (
    select alias from public.cross_parent_aliases  where parent_code = p_fish_code
  ),
  alleles as (
    select
      ta.transgene_base_code as base,
      ta.allele_number       as num,
      nullif(ta.allele_nickname, '') as nick
    from public.fish AS f
    join public.fish_transgene_alleles AS fta
      on fta.fish_id = f.id
    join public.transgene_alleles AS ta
      on ta.transgene_base_code = fta.transgene_base_code
     and ta.allele_number       = fta.allele_number
    where f.fish_code = p_fish_code
  ),
  built as (
    select string_agg(public._allele_display(base,num,nick), ' + ' order by base, num) as g
    from alleles
  )
  select
    coalesce( (select alias from alias),
              nullif((select g from built), ''),
              p_fish_code )
$$;

-- 4) Cross genotype = mom_genotype × dad_genotype
create or replace function public.gen_cross_genotype(p_mom text, p_dad text)
returns text
language sql
stable
as $$
  select public.gen_fish_genotype(p_mom) || ' × ' || public.gen_fish_genotype(p_dad)
$$;

-- 5) Recompute cross_name_genotype for all crosses
update public.crosses
set cross_name_genotype = public.gen_cross_genotype(mother_code, father_code);

commit;
