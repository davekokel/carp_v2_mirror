BEGIN;

create temp table _map(old text, new text) on commit drop;
insert into _map(old,new) values
  ('v_fish_overview_final','v_fish'),
  ('v_fish_overview_with_label_final','v_tank_labels'),
  ('v_fish_overview_with_label','v_tank_labels'),
  ('v_tanks_current_status_enriched','v_tanks'),
  ('v_tanks_current_status','v_tanks'),
  ('v_tank_pairs_base','v_tank_pairs'),
  ('v_plasmids_overview_final','v_plasmids'),
  ('v_plasmids_overview','v_plasmids'),
  ('v_clutch_annotations_summary_enriched','v_clutch_annotations'),
  ('v_clutch_annotations_summary','v_clutch_annotations'),
  ('v_clutch_treatments_summary_enriched','v_clutch_treatments'),
  ('v_clutch_treatments_summary','v_clutch_treatments'),
  ('v_fish_standard','v_fish'),
  ('v_fish_standard_clean_v2','v_fish');

do $$
declare r record; def text; def_new text; m record;
begin
  for r in select schemaname, viewname from pg_views where schemaname='public' loop
    def := pg_get_viewdef((quote_ident(r.schemaname)||'.'||quote_ident(r.viewname))::regclass, true);
    def_new := def;
    for m in select * from _map loop
      def_new := replace(def_new, 'public.'||m.old, 'public.'||m.new);
      def_new := replace(def_new, m.old, m.new);
    end loop;
    if def_new is distinct from def then
      execute 'create or replace view '||quote_ident(r.schemaname)||'.'||quote_ident(r.viewname)||' as '||def_new;
    end if;
  end loop;
end$$;

do $$
declare r record; cnt int;
begin
  for r in select distinct old from _map loop
    select count(*) into cnt
    from information_schema.view_table_usage
    where view_schema='public' and table_name=r.old;
    if cnt=0 then
      execute format('drop view if exists public.%I', r.old);
    end if;
  end loop;
end$$;

create temp table _still(dep text, legacy text) on commit drop;
insert into _still
select distinct vtu.view_name, vtu.table_name
from information_schema.view_table_usage vtu
join (select distinct old from _map) m on m.old=vtu.table_name
where vtu.view_schema='public';

COMMIT;

SELECT * FROM _still ORDER BY dep, legacy;
