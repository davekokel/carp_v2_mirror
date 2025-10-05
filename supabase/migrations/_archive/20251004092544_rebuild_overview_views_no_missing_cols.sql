BEGIN;

create or replace view public.vw_fish_overview_with_label as
with base as (
  select
    v.id,
    v.fish_code,
    v.name,
    v.transgene_base_code_filled,
    v.allele_code_filled,
    v.allele_name_filled,
    v.created_at,
    v.created_by,
    null::text as nickname,
    null::text as line_building_stage,
    f.date_birth,
    coalesce(f.created_by, v.created_by) as created_by_enriched
  from public.v_fish_overview v
  left join public.fish f
    on f.fish_code = v.fish_code
),
prefer_code as (
  select
    b.*,
    coalesce(
      substring(b.fish_code from '^FSH-([0-9]{8}-[0-9]{6})'),
      b.fish_code
    ) as batch_label
  from base b
)
select
  p.id,
  p.fish_code,
  p.name,
  p.transgene_base_code_filled,
  p.allele_code_filled,
  p.allele_name_filled,
  p.created_at,
  p.created_by,
  p.nickname,
  p.line_building_stage,
  p.date_birth,
  p.batch_label,
  p.created_by_enriched,
  null::timestamptz as last_plasmid_injection_at,
  null::text        as plasmid_injections_text,
  null::timestamptz as last_rna_injection_at,
  null::text        as rna_injections_text
from prefer_code p;

COMMIT;
