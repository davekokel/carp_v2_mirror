begin;

create or replace view public.v_fish_overview_human as
with
close_col as (
  select case
           when exists (
             select 1 from information_schema.columns
             where table_schema='public' and table_name='fish_tank_memberships' and column_name='left_at'
           ) then 'left_at'
           when exists (
             select 1 from information_schema.columns
             where table_schema='public' and table_name='fish_tank_memberships' and column_name='ended_at'
           ) then 'ended_at'
           else null
         end as col
),
open_memberships as (
  select m.fish_id, c.id as container_id, c.tank_code, c.label, c.status, c.created_at
  from public.fish_tank_memberships m
  join public.containers c on c.id = m.container_id
  left join close_col cc on true
  where (
           cc.col is null
        or (cc.col = 'left_at'  and m.left_at  is null)
        or (cc.col = 'ended_at' and m.ended_at is null)
        )
    and (c.status in ('active','new_tank') or c.status is null)
),
alleles as (
  select
    fta.fish_id,
    fta.transgene_base_code as base_code,
    fta.allele_number,
    coalesce(ta.allele_nickname, cast(fta.allele_number as text)) as allele_nickname,
    tg.transgene_name,
    fta.zygosity
  from public.fish_transgene_alleles fta
  left join public.transgene_alleles ta
    on ta.transgene_base_code = fta.transgene_base_code
   and ta.allele_number       = fta.allele_number
  left join public.transgenes tg
    on tg.transgene_base_code = fta.transgene_base_code
),
genotype as (
  select
    a.fish_id,
    string_agg(
      trim(both ' ' from
        coalesce(a.transgene_name, a.base_code) || '(' || a.allele_number::text ||
        coalesce(' '||a.zygosity, '') || ')'
      ),
      ' + ' order by a.base_code, a.allele_number
    ) as genotype_rollup,
    min(coalesce(a.transgene_name, a.base_code)) as transgene_primary,
    min(a.allele_number) as allele_number_primary,
    min(coalesce(a.transgene_name, a.base_code) || '(' || a.allele_number::text || ')') as allele_code_primary
  from alleles a
  group by a.fish_id
),
current_tank as (
  select distinct on (o.fish_id)
    o.fish_id, o.tank_code, o.label as tank_label, o.status as tank_status, o.created_at as tank_created_at
  from open_memberships o
  order by o.fish_id, o.created_at desc nulls last
)
select
  f.id                 as fish_id,
  f.fish_code          as fish_code,
  f.name               as fish_name,
  f.nickname           as fish_nickname,
  f.genetic_background as genetic_background,
  g.allele_number_primary as allele_number,
  g.allele_code_primary   as allele_code,
  g.transgene_primary     as transgene,
  g.genotype_rollup       as genotype_rollup,
  ct.tank_code         as tank_code,
  ct.tank_label        as tank_label,
  ct.tank_status       as tank_status,
  f.stage              as stage,
  f.date_birth         as date_birth,
  f.created_at         as created_at,
  f.created_by         as created_by
from public.fish f
left join genotype g     on g.fish_id = f.id
left join current_tank ct on ct.fish_id = f.id
order by f.created_at desc nulls last;

commit;
