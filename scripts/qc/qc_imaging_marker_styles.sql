\set ON_ERROR_STOP on

select
  (select count(*) from public.v_roi_overview) as n_rois,
  (select count(*) from public.v_roi_overview where coalesce(btrim(genotype_code),'') <> '') as n_rois_with_genotype_code,
  (select count(distinct genotype_code) from public.v_roi_overview where coalesce(btrim(genotype_code),'') <> '') as n_distinct_genotype_codes_in_rois,
  (select count(distinct vo.genotype_code)
   from public.v_roi_overview vo
   join public.v_genotype_marker_styles_strict gms using (genotype_code)
   where coalesce(btrim(vo.genotype_code),'') <> '') as n_distinct_genotype_codes_in_rois_with_gms
;

with vo_codes as (
  select distinct genotype_code
  from public.v_roi_overview
  where coalesce(btrim(genotype_code),'') <> ''
),
j as (
  select
    c.genotype_code,
    gv.genotype_basecodes,
    gms.genotype_fluortag_style,
    gms.genotype_fluororganelle_style
  from vo_codes c
  left join public.genotypes_v11 gv
    on gv.genotype_code = c.genotype_code
  left join public.v_genotype_marker_styles_strict gms
    on gms.genotype_code = c.genotype_code
)
select *
from j
order by genotype_code
;

with geno_base as (
  select distinct lower(m[1]) as base_code
  from public.genotypes_v11 gv
  cross join lateral regexp_split_to_table(replace(gv.genotype_basecodes,'|',';'), '\s*;\s*') as tok(tok)
  cross join lateral regexp_matches(tok.tok, '^\s*([a-z0-9-]+)\s*(?::\s*\d+)?\s*$', 'i') as m
  where coalesce(btrim(gv.genotype_basecodes),'') <> ''
),
missing as (
  select g.base_code
  from geno_base g
  left join public.v_construct_marker_styles vcms using (base_code)
  where vcms.base_code is null
)
select
  (select count(*) from geno_base) as n_base_codes_in_genotypes,
  (select count(*) from missing) as n_missing_base_codes,
  (select string_agg(base_code, ', ' order by base_code) from missing) as missing_base_codes
;
