-- Drop the old view (if any), then recreate with the exact column list the UI expects
drop view if exists public.v_fish_overview;

create view public.v_fish_overview
  (fish_code, name, nickname, genotype, genetic_background, stage, date_birth, created_at, created_by, batch_display)
as
select
  v.fish_code,
  coalesce(v.fish_name, '')                        as name,
  coalesce(v.nickname, '')                         as nickname,
  coalesce(v.transgene_pretty_filled,
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
