begin;
create or replace function public._table_has(col_table_schema text, col_table_name text, col_name text)
returns boolean language sql stable as $$
  select exists (
    select 1 from information_schema.columns
    where table_schema=col_table_schema and table_name=col_table_name and column_name=col_name
  )
$$;
commit;
