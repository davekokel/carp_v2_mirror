begin;

drop view if exists public.v_fish_overview cascade;
create view public.v_fish_overview as
select
    f.id,
    f.fish_code,
    f.name,
    null::text as allele_name_filled,
    f.created_at,
    f.created_by,
    (
        select array_to_string(array_agg(x.base), ', ')
        from (
            select distinct t.transgene_base_code as base
            from public.fish_transgene_alleles as t
            where t.fish_id = f.id
            order by base
        ) as x
    ) as transgene_base_code_filled,
    (
        select array_to_string(array_agg(x.an), ', ')
        from (
            select distinct t.allele_number::text as an
            from public.fish_transgene_alleles as t
            where t.fish_id = f.id
            order by an
        ) as x
    ) as allele_code_filled
from public.fish as f
where
    exists (
        select 1 from public.fish_transgene_alleles as t
        where t.fish_id = f.id
    )
order by f.created_at desc;

drop view if exists public.vw_fish_overview_with_label cascade;
do $$
declare
  has_nickname boolean;
  has_line     boolean;
  has_birth    boolean;
begin
  select exists(
           select 1 from information_schema.columns
            where table_schema='public' and table_name='fish' and column_name='nickname'
         ) into has_nickname;

  select exists(
           select 1 from information_schema.columns
            where table_schema='public' and table_name='fish' and column_name='line_building_stage'
         ) into has_line;

  select exists(
           select 1 from information_schema.columns
            where table_schema='public' and table_name='fish' and column_name='date_birth'
         ) into has_birth;

  execute format($v$
    create view public.vw_fish_overview_with_label as
    select
      v.id,
      v.fish_code,
      v.name,
      v.transgene_base_code_filled,
      v.allele_code_filled,
      v.allele_name_filled,
      v.created_at,
      v.created_by,
      null::text as transgene_pretty,
      %s as nickname,
      %s as line_building_stage,
      %s as date_birth,
      null::text as batch_label,
      null::text as created_by_enriched,
      null::timestamptz as last_plasmid_injection_at,
      null::text as plasmid_injections_text,
      null::timestamptz as last_rna_injection_at,
      null::text as rna_injections_text
    from public.v_fish_overview v
    left join public.fish f on f.id = v.id
  $v$,
    case when has_nickname then 'f.nickname'        else 'null::text' end,
    case when has_line     then 'f.line_building_stage' else 'null::text' end,
    case when has_birth    then 'f.date_birth'       else 'null::date' end
  );
end$$;

commit;
