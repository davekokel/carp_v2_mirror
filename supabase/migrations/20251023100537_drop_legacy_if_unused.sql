BEGIN;
create temp table _legacy(name text) on commit drop;
insert into _legacy(name) values
  ('v_fish_standard'),
  ('v_fish_standard_clean_v2'),
  ('v_fish_label_fields'),
  ('v_fish_live_counts'),
  ('v_cit_rollup'),
  ('v_rna_plasmids'),
  ('v_fish_overview_with_label'),
  ('v_clutch_annotations_summary'),
  ('v_clutch_treatments_summary'),
  ('v_tanks_current_status'),
  ('v_plasmids_overview'),
  ('v_tank_pairs_base'),
  ('v_plasmids_overview_final'),
  ('v_clutch_annotations_summary_enriched'),
  ('v_clutch_treatments_summary_enriched'),
  ('v_tanks_current_status_enriched'),
  ('v_fish_overview_final'),
  ('v_fish_overview_with_label_final');

do $$
declare r record; cnt int;
begin
  for r in select name from _legacy loop
    select count(*) into cnt
    from information_schema.view_table_usage
    where view_schema='public' and table_name=r.name;
    if cnt=0 then
      execute format('drop view if exists public.%I', r.name);
    end if;
  end loop;
end$$;

COMMIT;
