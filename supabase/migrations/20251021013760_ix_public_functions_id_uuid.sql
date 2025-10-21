do $do$
declare
  r record;
  def text;
begin
  for r in
    select p.oid
    from pg_proc p
    join pg_namespace n on n.oid=p.pronamespace
    where n.nspname='public'
      and pg_get_functiondef(p.oid) like '%id_uuid%'
  loop
    select pg_get_functiondef(r.oid) into def;
    def := replace(def, 'id_uuid', 'id');
    execute def;
  end loop;
end
$do$;
