do $$
declare
  r record;
  def text;
begin
  for r in
    select p.oid
    from pg_proc p
    join pg_namespace n on n.oid=p.pronamespace
    where n.nspname='public'
      and pg_get_functiondef(p.oid) like '%public.plasmids%'
      and pg_get_functiondef(p.oid) like '%id_uuid%'
  loop
    select pg_get_functiondef(r.oid) into def;
    def := replace(def, 'id_uuid', 'id');
    execute def;
  end loop;

  for r in
    select c.oid
    from pg_class c
    join pg_namespace n on n.oid=c.relnamespace
    where c.relkind='v'
      and n.nspname='public'
      and pg_get_viewdef(c.oid,true) like '%public.plasmids%'
      and pg_get_viewdef(c.oid,true) like '%id_uuid%'
  loop
    select pg_get_viewdef(r.oid,true) into def;
    def := replace(def, 'id_uuid', 'id');
    execute format('create or replace view %s as %s', (select quote_ident(n.nspname)||'.'||quote_ident(c.relname) from pg_class c join pg_namespace n on n.oid=c.relnamespace where c.oid=r.oid), def);
  end loop;
end$$;
