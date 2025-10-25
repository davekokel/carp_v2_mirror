BEGIN;

create temp table _rename_map(old text, new text) on commit drop;
insert into _rename_map(old,new) values
  ('vw_fish_overview_with_label','v_fish_overview_with_label'),
  ('vw_fish_standard','v_fish_standard'),
  ('vw_plasmids_overview','v_plasmids_overview');

create temp table _targets(schema_name text, view_name text) on commit drop;
insert into _targets(schema_name, view_name)
select distinct vtu.view_schema, vtu.view_name
from information_schema.view_table_usage vtu
where vtu.view_schema='public'
  and vtu.table_name in (select old from _rename_map);

do $$
declare
  r record;
  def text;
  def_new text;
  m record;
begin
  for r in select * from _targets loop
    def := pg_get_viewdef((quote_ident(r.schema_name)||'.'||quote_ident(r.view_name))::regclass, true);
    def_new := def;
    for m in select * from _rename_map loop
      def_new := replace(def_new, 'public.'||m.old, 'public.'||m.new);
      def_new := replace(def_new, m.old, m.new);
    end loop;
    if def_new is distinct from def then
      execute 'create or replace view '
              || quote_ident(r.schema_name) || '.' || quote_ident(r.view_name)
              || ' as ' || def_new;
    end if;
  end loop;
end$$;

do $$
declare
  leftovers text[];
begin
  select array_agg(distinct vtu.view_name)
  into leftovers
  from information_schema.view_table_usage vtu
  where vtu.view_schema='public'
    and vtu.table_name in ('vw_fish_overview_with_label','vw_fish_standard','vw_plasmids_overview');
  if leftovers is not null then
    raise exception 'Cannot drop vw_*; still referenced by: %', leftovers;
  end if;
end$$;

drop view if exists public.vw_fish_overview_with_label;
drop view if exists public.vw_fish_standard;
drop view if exists public.vw_plasmids_overview;

COMMIT;
