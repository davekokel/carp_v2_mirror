begin;

-- Robust: choose the real base-code column, then INSERT ... ON CONFLICT using dynamic SQL
create or replace function public.ensure_transgene_base(p_base text)
returns void
language plpgsql
as $$
declare
  v_col text;
  v_sql text;
begin
  -- Decide which column the current schema exposes
  select
    case
      when exists (
        select 1 from information_schema.columns
        where table_schema = 'public'
          and table_name   = 'transgenes'
          and column_name  = 'transgene_base_code'
      ) then 'transgene_base_code'
      when exists (
        select 1 from information_schema.columns
        where table_schema = 'public'
          and table_name   = 'transgenes'
          and column_name  = 'base_code'
      ) then 'base_code'
      else null
    end
  into v_col;

  if v_col is null then
    raise exception 'transgenes table is missing a base-code column (expected transgene_base_code or base_code)';
  end if;

  -- Insert the base row if missing, conflict on the discovered column
  v_sql := format(
    'insert into public.transgenes (%I) values ($1) on conflict (%I) do nothing',
    v_col, v_col
  );
  execute v_sql using p_base;
end
$$;

commit;
