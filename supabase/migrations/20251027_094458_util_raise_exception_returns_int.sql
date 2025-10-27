create or replace function public.raise_exception(msg text)
returns int
language plpgsql
as $$
begin
  raise exception '%', msg;
  return 0;
end;
$$;
