DROP VIEW IF EXISTS public.v_fish_overview CASCADE;
-- Drop the old view (if any), then recreate with the exact column list the UI expects
drop view if exists public.v_fish_overview;

create or replace view public.v_fish_overview
  (fish_code, name, nickname, genotype, genetic_background, stage, date_birth, created_at, created_by, batch_display)
as
select
  v.fish_code,
  coalesce(v.name, '')                        as name,
  coalesce(v.nickname, '')                         as nickname,
  coalesce('',
           '',
           v.allele_name_filled,
           v.allele_code_filled,
           '')                                      as genotype,
  null::text                                       as genetic_background,
  coalesce(v.line_building_stage, '')              as stage,
  NULL::date                                  as date_birth,
  null::timestamptz                                as created_at,
  coalesce(v.created_by, '')                       as created_by,
  coalesce(v.batch_label, '')                      as batch_display
from public.v_fish_overview_with_label v;
