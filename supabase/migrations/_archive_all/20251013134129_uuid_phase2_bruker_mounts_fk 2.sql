begin;

-- 1) add the new UUID FK column if missing
alter table public.bruker_mounts
  add column if not exists selection_id_uuid uuid;

-- 2) backfill selection_id_uuid depending on the current type of selection_id
DO $$
BEGIN
declare v_typ text;
begin
  select data_type
    into v_typ
  from information_schema.columns
  where table_schema='public'
    and table_name='bruker_mounts'
    and column_name='selection_id';

  if v_typ = 'uuid' then
    -- simple copy when selection_id is already uuid
    update public.bruker_mounts
       set selection_id_uuid = selection_id
     where selection_id_uuid is null;
  else
    -- selection_id is text/int/etc. — resolve via either legacy int id or id_uuid
    update public.bruker_mounts b
       set selection_id_uuid = ci.id_uuid
      from public.clutch_instances ci
     where b.selection_id_uuid is null
       and (
         b.selection_id::text = ci.id_uuid::text
         or b.selection_id::text = ci.id::text
       );

    -- optional: last-chance parse if selection_id looks like a UUID literal
    update public.bruker_mounts
       set selection_id_uuid = selection_id::uuid
     where selection_id_uuid is null
       and selection_id::text ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$';
  end if;
end;
END;
$$ LANGUAGE plpgsql;

-- 3) index + FK constraint on the new UUID column
create index if not exists ix_bm_selection_id_uuid on public.bruker_mounts(selection_id_uuid);
alter table public.bruker_mounts
  add constraint fk_bm_selection_uuid
  foreign key (selection_id_uuid)
  references public.clutch_instances(id_uuid)
  on delete restrict;

commit;
