alter table audit.writes add column if not exists app_user text;

create or replace function audit.fn_writes() returns trigger
language plpgsql as $$
declare
  pk text;
  who text := current_setting('app.user', true);
begin
  pk := coalesce(
    (to_jsonb(coalesce(NEW,OLD))->>'id'),
    (to_jsonb(coalesce(NEW,OLD))->>'id_uuid'),
    (to_jsonb(coalesce(NEW,OLD))->>'fish_code'),
    (to_jsonb(coalesce(NEW,OLD))->>'tank_code')
  );
  if TG_OP = 'INSERT' then
    insert into audit.writes(table_name,op,user_name,app_user,client_addr,row_pk,new_row)
    values (TG_TABLE_NAME,'I',session_user,who,inet_client_addr(),pk,to_jsonb(NEW));
    return NEW;
  elsif TG_OP = 'UPDATE' then
    insert into audit.writes(table_name,op,user_name,app_user,client_addr,row_pk,old_row,new_row)
    values (TG_TABLE_NAME,'U',session_user,who,inet_client_addr(),pk,to_jsonb(OLD),to_jsonb(NEW));
    return NEW;
  else
    insert into audit.writes(table_name,op,user_name,app_user,client_addr,row_pk,old_row)
    values (TG_TABLE_NAME,'D',session_user,who,inet_client_addr(),pk,to_jsonb(OLD));
    return OLD;
  end if;
end
$$;
