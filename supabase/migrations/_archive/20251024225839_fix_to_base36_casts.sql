begin;
create or replace function public.to_base36(n bigint)
returns text
language plpgsql
immutable
as $$
declare
  v bigint := n;
  s text := '';
  a constant text := '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ';
  pos integer;
begin
  if v < 0 then
    raise exception 'to_base36 expects nonnegative';
  end if;
  if v = 0 then
    return '0';
  end if;
  while v > 0 loop
    pos := (v % 36)::int + 1;
    s := substr(a, pos, 1) || s;
    v := v / 36;
  end loop;
  return s;
end
$$;
commit;
