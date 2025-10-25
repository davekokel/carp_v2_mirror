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
      and p.proname='upsert_fish_by_batch_name_dob'
  loop
    select pg_get_functiondef(r.oid) into def;
    if def is not null then
      def := replace(def, 'id_uuid', 'id');
      execute def;
    end if;
  end loop;
end$$;
