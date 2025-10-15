-- Compat view for the UI: expose the columns load_fish_overview() expects.
create or replace view public.v_fish_overview as
select
  v.fish_code,
  coalesce(v.name, '')                        as name,
  coalesce(v.nickname, '')                         as nickname,
  coalesce(coalesce(v.transgene_pretty, v.genotype_pretty, ''),
           v.transgene_pretty_nickname,
           v.allele_name_filled,
           v.allele_code_filled,
           '')                                      as genotype,
  null::text                                       as genetic_background,
  coalesce(v.line_building_stage, '')              as stage,
  v.date_of_birth                                  as date_birth,
  null::timestamptz                                as created_at,
  coalesce(v.created_by, '')                       as created_by,
  coalesce(v.batch_label, '')                      as batch_display
from public.vw_fish_overview_with_label v;
