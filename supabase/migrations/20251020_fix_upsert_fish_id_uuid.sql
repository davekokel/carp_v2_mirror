do $$
declare
  def text;
begin
  select pg_get_functiondef(oid)
    into def
  from pg_proc
  where proname='upsert_fish_by_batch_name_dob'
  order by oid desc
  limit 1;

  if def is null then
    raise notice 'function upsert_fish_by_batch_name_dob not found';
  else
    def := replace(def, 'id_uuid', 'id');
    execute def;
  end if;
end$$;
