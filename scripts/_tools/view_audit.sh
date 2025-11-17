#!/usr/bin/env bash
set -euo pipefail
STAMP=$(date +%Y%m%d%H%M%S)
OUT="priming/view_audit_$STAMP"
mkdir -p "$OUT"

psql "$DB_URL" -Atc "\copy (
with v(v) as (values
  ('v_fish'),('v_tank_labels'),('v_tanks'),
  ('v_tank_pairs'),('v_plasmids'),('v_clutch_annotations'),('v_clutch_treatments')
), defs as (
  select v, pg_get_viewdef(('public.'||v)::regclass, true) as def from v
)
select v as view_name, position(v in def)>0 as self_reference
from defs order by view_name
) to '$OUT/self_reference.csv' with csv header"

psql "$DB_URL" -Atc "\copy (
with v(v) as (values
  ('v_fish'),('v_tank_labels'),('v_tanks'),
  ('v_tank_pairs'),('v_plasmids'),('v_clutch_annotations'),('v_clutch_treatments')
), defs as (
  select v, pg_get_viewdef(('public.'||v)::regclass, true) as def from v
), legacy(name) as (values
  ('vw_'),('v_%_final'),('v_%_enriched'),('v_%_base'),
  ('v_fish_standard'),('v_fish_standard_clean_v2'),
  ('v_fish_label_fields'),('v_fish_live_counts'),
  ('v_cit_rollup'),('v_rna_plasmids'),
  ('v_plasmids_overview'),('v_tanks_current_status'),
  ('v_clutch_annotations_summary'),('v_clutch_treatments_summary')
)
select d.v as view_name, l.name as legacy_pattern
from defs d join legacy l on d.def like '%'||replace(l.name,'_','\_')||'%' escape '\'
order by d.v, l.name
) to '$OUT/legacy_refs.csv' with csv header"

psql "$DB_URL" -Atc "\copy (
select table_name as view_name, ordinal_position, column_name, data_type
from information_schema.columns
where table_schema='public'
  and table_name in ('v_fish','v_tank_labels','v_tanks','v_tank_pairs','v_plasmids','v_clutch_annotations','v_clutch_treatments')
order by table_name, ordinal_position
) to '$OUT/column_signatures.csv' with csv header"

printf "%s\n" "$OUT"
