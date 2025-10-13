begin;

alter table public.bruker_mounts
  add column if not exists selection_id_uuid uuid;

-- backfill from existing selection_id
do $$
declare v_typ text;
begin
  select data_type
    into v_typ
  from information_schema.columns
  where table_schema='public'
    and table_name='bruker_mounts'
    and column_name='selection_id';

  if v_typ = 'uuid' then
    update public.bruker_mounts
       set selection_id_uuid = selection_id
     where selection_id_uuid is null;
  else
    update public.bruker_mounts b
       set selection_id_uuid = ci.id_uuid
      from public.clutch_instances ci
     where b.selection_id_uuid is null
       and (
         b.selection_id::text = ci.id_uuid::text
         or b.selection_id::text = ci.id::text
       );

    update public.bruker_mounts
       set selection_id_uuid = selection_id::uuid
     where selection_id_uuid is null
       and selection_id::text ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$';
  end if;
end$$;

create index if not exists ix_bm_selection_id_uuid on public.bruker_mounts(selection_id_uuid);

commit;
