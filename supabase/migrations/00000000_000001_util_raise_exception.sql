create or replace function public.raise_exception(msg text)
returns void
language plpgsql
as $$
begin
  raise exception '%', msg;
end;
$$;
