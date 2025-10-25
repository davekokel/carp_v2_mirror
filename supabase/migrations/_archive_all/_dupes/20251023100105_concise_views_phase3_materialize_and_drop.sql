BEGIN;

create temp table _pairs(legacy text, concise text) on commit drop;
insert into _pairs values
  ('v_fish_overview_final','v_fish'),
  ('v_fish_overview_with_label_final','v_tank_labels'),
  ('v_tanks_current_status_enriched','v_tanks'),
  ('v_tank_pairs_base','v_tank_pairs'),
  ('v_plasmids_overview_final','v_plasmids'),
  ('v_clutch_annotations_summary_enriched','v_clutch_annotations'),
  ('v_clutch_treatments_summary_enriched','v_clutch_treatments');

do $$
declare r record; def text;
begin
  for r in select * from _pairs loop
    if to_regclass('public.'||r.legacy) is not null then
      def := pg_get_viewdef(('public.'||r.legacy)::regclass, true);
      execute 'create or replace view public.'||r.concise||' as '||def;
    end if;
  end loop;
end$$;

do $$
declare leftovers text[];
begin
  select array_agg(distinct vtu.view_name)
  into leftovers
  from information_schema.view_table_usage vtu
  where vtu.view_schema='public'
    and vtu.table_name in (select legacy from _pairs);
  if leftovers is not null then
    raise exception 'Cannot drop legacy; still referenced by: %', leftovers;
  end if;
end$$;

drop view if exists public.v_fish_overview_final;
drop view if exists public.v_fish_overview_with_label_final;
drop view if exists public.v_tanks_current_status_enriched;
drop view if exists public.v_tank_pairs_base;
drop view if exists public.v_plasmids_overview_final;
drop view if exists public.v_clutch_annotations_summary_enriched;
drop view if exists public.v_clutch_treatments_summary_enriched;

COMMIT;
