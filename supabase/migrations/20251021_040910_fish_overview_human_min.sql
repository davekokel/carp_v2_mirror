begin;

-- Minimal compatibility view for pages expecting v_fish_overview_human
create or replace view public.v_fish_overview_human as
select
  f.id                               as fish_id,
  f.fish_code                        as fish_code,
  f.name                             as fish_name,
  f.nickname                         as fish_nickname,
  f.genetic_background               as genetic_background,
  null::int                          as allele_number,
  null::text                         as allele_code,
  null::text                         as transgene,
  null::text                         as genotype_rollup,
  vt.tank_code                       as tank_code,
  null::text                         as tank_label,
  vt.status                          as tank_status,
  f.line_building_stage              as stage,
  f.date_birth                       as date_birth,
  f.created_at                       as created_at,
  f.created_by                       as created_by
from public.fish f
left join public.v_tanks vt on vt.fish_id = f.id;

commit;
