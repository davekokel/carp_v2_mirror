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
    f.nickname,
    f.line_building_stage,
    f.date_birth,
    f.created_by as created_by_enriched
  from public.v_fish_overview v
  left join public.fish f
    on f.id_uuid = v.id
),
prefer_seed as (
  select
    b.*,
    coalesce(
      (
        select ll.seed_batch_id
        from public.load_log_fish ll
        where ll.fish_id = b.id
        order by ll.logged_at desc
        limit 1
      ),
      regexp_replace(b.fish_code, '^FSH-([0-9]{8}-[0-9]{6})-.*$', '\1')
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
from prefer_seed p;

COMMIT;
