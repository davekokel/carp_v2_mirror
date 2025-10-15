create schema if not exists audit;

create table if not exists audit.writes (
  id           bigserial primary key,
  at           timestamptz not null default now(),
  table_name   text not null,
  op           text not null, -- I/U/D
  user_name    text not null default session_user,
  client_addr  inet,
  row_pk       text,
  new_row      jsonb,
  old_row      jsonb
);

create or replace function audit.fn_writes() returns trigger
language plpgsql as $$
declare
  pk text;
begin
  pk := coalesce(
    (to_jsonb(coalesce(NEW,OLD))->>'id'),
    (to_jsonb(coalesce(NEW,OLD))->>'id_uuid'),
    (to_jsonb(coalesce(NEW,OLD))->>'fish_code'),
    (to_jsonb(coalesce(NEW,OLD))->>'tank_code')
  );
  if TG_OP = 'INSERT' then
    insert into audit.writes(table_name,op,user_name,client_addr,row_pk,new_row)
    values (TG_TABLE_NAME,'I',session_user,inet_client_addr(),pk,to_jsonb(NEW));
    return NEW;
  elsif TG_OP = 'UPDATE' then
    insert into audit.writes(table_name,op,user_name,client_addr,row_pk,old_row,new_row)
    values (TG_TABLE_NAME,'U',session_user,inet_client_addr(),pk,to_jsonb(OLD),to_jsonb(NEW));
    return NEW;
  else
    insert into audit.writes(table_name,op,user_name,client_addr,row_pk,old_row)
    values (TG_TABLE_NAME,'D',session_user,inet_client_addr(),pk,to_jsonb(OLD));
    return OLD;
  end if;
end
$$;

create or replace function audit.attach_writes(t regclass) returns void
language plpgsql as $$
begin
  execute format('drop trigger if exists trg_audit_ins on %s', t);
  execute format('drop trigger if exists trg_audit_upd on %s', t);
  execute format('drop trigger if exists trg_audit_del on %s', t);

  execute format('create trigger trg_audit_ins after insert on %s for each row execute function audit.fn_writes()', t);
  execute format('create trigger trg_audit_upd after update on %s for each row execute function audit.fn_writes()', t);
  execute format('create trigger trg_audit_del after delete on %s for each row execute function audit.fn_writes()', t);
end
$$;

select audit.attach_writes('public.fish'::regclass);
select audit.attach_writes('public.transgene_alleles'::regclass);
select audit.attach_writes('public.fish_transgene_alleles'::regclass);
select audit.attach_writes('public.containers'::regclass);
select audit.attach_writes('public.fish_tank_memberships'::regclass);
