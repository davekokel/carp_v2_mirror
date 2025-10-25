BEGIN;

create temp table _legacy(name text) on commit drop;
insert into _legacy(name) values
  ('v_fish_standard'),
  ('v_fish_standard_clean_v2'),
  ('v_fish_label_fields'),
  ('v_fish_live_counts'),
  ('v_cit_rollup'),
  ('v_rna_plasmids'),
  ('v_fish_overview_final'),
  ('v_fish_overview_with_label_final'),
  ('v_tanks_current_status_enriched'),
  ('v_tank_pairs_base'),
  ('v_plasmids_overview_final'),
  ('v_clutch_annotations_summary_enriched'),
  ('v_clutch_treatments_summary_enriched');

do $$
declare leftovers text[];
begin
  select array_agg(distinct vtu.view_name)
  into leftovers
  from information_schema.view_table_usage vtu
  where vtu.view_schema='public'
    and vtu.table_name in (select name from _legacy);

  if leftovers is not null then
    raise exception 'Cannot drop legacy; still referenced by: %', leftovers;
  end if;
end$$;

-- Drop whatever still exists from the legacy list
do $$
declare r record;
begin
  for r in select name from _legacy loop
    execute format('drop view if exists public.%I', r.name);
  end loop;
end$$;

COMMIT;
