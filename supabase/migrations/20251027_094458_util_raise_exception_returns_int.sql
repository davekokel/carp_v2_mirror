drop function if exists public.raise_exception(text);
create function public.raise_exception(msg text)
returns int
language plpgsql
as $fn$
begin
  raise exception '%', msg;
  return 0;
end;
$fn$;
