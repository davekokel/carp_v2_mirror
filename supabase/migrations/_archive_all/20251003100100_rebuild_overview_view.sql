begin;

-- Recreate v_fish_overview so it tolerates missing optional columns/tables.
do $$
declare
  fish_pk text := coalesce(util_mig.pk_col('public','fish'), 'id');
  has_name boolean := public._table_has('public','fish','name');
  has_created_at boolean := public._table_has('public','fish','created_at');
  has_created_by boolean := public._table_has('public','fish','created_by');
  has_fish_code boolean := public._table_has('public','fish','fish_code');
  has_fta boolean := util_mig.table_exists('public','fish_transgene_alleles');
  select_list text := '';
  ddl text;
begin
  -- id (always)
  select_list := format('f.%1$I as id', fish_pk);

  -- fish_code (optional)
  if has_fish_code then
    select_list := select_list || ', f.fish_code';
  else
    select_list := select_list || ', null::text as fish_code';
  end if;

  -- name (optional)
  if has_name then
    select_list := select_list || ', f.name';
  else
    select_list := select_list || ', null::text as name';
  end if;

  -- transgene_base_code_filled + allele_code_filled (only if fish_transgene_alleles exists)
  if has_fta then
    select_list := select_list || format($frag$
      , (
          select array_to_string(array_agg(x.base_code), ', ')
          from (
            select distinct t.transgene_base_code as base_code
            from public.fish_transgene_alleles t
            where t.fish_id = f.%1$I
            order by t.transgene_base_code
          ) x
        ) as transgene_base_code_filled
      , (
          select array_to_string(array_agg(x.allele_text), ', ')
          from (
            select distinct (t.allele_number::text) as allele_text
            from public.fish_transgene_alleles t
            where t.fish_id = f.%1$I
            order by (t.allele_number::text)
          ) x
        ) as allele_code_filled
    $frag$, fish_pk);
  else
    select_list := select_list || ', null::text as transgene_base_code_filled, null::text as allele_code_filled';
  end if;

  -- allele_name_filled placeholder
  select_list := select_list || ', null::text as allele_name_filled';

  -- created_at / created_by (optional)
  if has_created_at then
    select_list := select_list || ', f.created_at';
  else
    select_list := select_list || ', null::timestamptz as created_at';
  end if;

  if has_created_by then
    select_list := select_list || ', f.created_by';
  else
    select_list := select_list || ', null::text as created_by';
  end if;

  ddl := format($v$
    drop view if exists public.v_fish_overview cascade;
    create view public.v_fish_overview as
    select
      %s
    from public.fish f;
  $v$, select_list);

  execute ddl;
end $$;

commit;
