begin;

-- A tiny toolbox for guarded, replayable migrations
create schema if not exists util_mig;

-- 1) Check if a table exists
create or replace function util_mig.table_exists(p_schema text, p_table text)
returns boolean language sql stable as $$
  select to_regclass(format('%I.%I', p_schema, p_table)) is not null
$$;

-- 2) Pick primary key column name, preferring id -> id_uuid
create or replace function util_mig.pk_col(p_schema text, p_table text)
returns text language plpgsql stable as $$
declare
  col text;
begin
  -- prefer 'id' when present
  select 'id'
    into col
  where exists (
    select 1 from information_schema.columns
    where table_schema=p_schema and table_name=p_table and column_name='id'
  );
  if col is not null then return col; end if;

  -- fallback to 'id_uuid'
  select 'id_uuid'
    into col
  where exists (
    select 1 from information_schema.columns
    where table_schema=p_schema and table_name=p_table and column_name='id_uuid'
  );
  return col; -- may be null if neither exists
end
$$;

-- 3) Ensure a UNIQUE index over given column list
create or replace function util_mig.ensure_unique(
  p_schema text, p_table text, p_index_name text, p_cols text[]
) returns void language plpgsql as $$
declare
  exists_idx boolean;
  cols_sql  text := (select string_agg(format('%I', c), ', ') from unnest(p_cols) c);
begin
  select exists(
    select 1 from pg_indexes
    where schemaname=p_schema and tablename=p_table and indexname=p_index_name
  ) into exists_idx;

  if not exists_idx then
    execute format('create unique index %I on %I.%I (%s)', p_index_name, p_schema, p_table, cols_sql);
  end if;
end
$$;

-- 4) Ensure a FOREIGN KEY constraint (idempotent) with optional ON DELETE action
create or replace function util_mig.ensure_fk(
  p_schema text, p_table text, p_cols text[],
  p_ref_schema text, p_ref_table text, p_ref_cols text[],
  p_constraint_name text, p_on_delete text default null
) returns void language plpgsql as $$
declare
  exists_fk boolean;
  cols_sql     text := (select string_agg(format('%I', c), ', ') from unnest(p_cols) c);
  ref_cols_sql text := (select string_agg(format('%I', c), ', ') from unnest(p_ref_cols) c);
  od_sql       text := case when p_on_delete is null then '' else ' on delete '||p_on_delete end;
begin
  select exists(
    select 1 from pg_constraint c
    join pg_class t on t.oid=c.conrelid
    join pg_namespace n on n.oid=t.relnamespace
    where c.contype='f'
      and n.nspname=p_schema
      and t.relname=p_table
      and c.conname=p_constraint_name
  ) into exists_fk;

  if not exists_fk then
    execute format(
      'alter table %I.%I add constraint %I foreign key (%s) references %I.%I (%s)%s',
      p_schema, p_table, p_constraint_name, cols_sql,
      p_ref_schema, p_ref_table, ref_cols_sql, od_sql
    );
  end if;
end
$$;

commit;
