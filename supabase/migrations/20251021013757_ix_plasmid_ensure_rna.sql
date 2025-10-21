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
      and p.proname in ('ensure_rna_for_plasmid','trg_plasmid_auto_ensure_rna')
  loop
    select pg_get_functiondef(r.oid) into def;
    if def like '%id_uuid%' then
      def := replace(def, 'id_uuid', 'id');
      execute def;
    end if;
  end loop;
end$$;
