begin;
create extension if not exists pgcrypto;
create or replace function public.digest(text, text)
returns bytea
language sql immutable parallel safe as
$$ select extensions.digest(convert_to($1,'UTF8'), $2); $$;
commit;
