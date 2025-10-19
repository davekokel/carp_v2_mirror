begin;

drop view if exists public.vw_fish_overview_with_label cascade;
drop view if exists public.v_fish_overview cascade;
do $$
declare has_fish boolean;
begin
  has_fish := to_regclass('public.fish') is not null;

  if has_fish then
    execute $v$
      create view public.v_fish_overview as
      select
        f.id,
        f.fish_code,
        f.name,
        (
          select array_to_string(array_agg(x.base), ', ')
          from (
            select distinct t.transgene_base_code as base
            from public.fish_transgene_alleles t
            where t.fish_id = f.id
            order by base
          ) x
        ) as transgene_base_code_filled,
        (
          select array_to_string(array_agg(x.an), ', ')
          from (
            select distinct (t.allele_number::text) as an
            from public.fish_transgene_alleles t
            where t.fish_id = f.id
            order by an
          ) x
        ) as allele_code_filled,
        null::text as allele_name_filled,
        f.created_at,
        f.created_by
      from public.fish f
      where exists (select 1 from public.fish_transgene_alleles t where t.fish_id = f.id)
      order by f.created_at desc
    $v$;
  else
    -- empty shape, allows downstream pages to query without errors
    execute $v$
      create view public.v_fish_overview as
      select
        null::uuid          as id,
        null::text          as fish_code,
        null::text          as name,
        null::text          as transgene_base_code_filled,
        null::text          as allele_code_filled,
        null::text          as allele_name_filled,
        null::timestamptz   as created_at,
        null::text          as created_by
      where false
    $v$;
  end if;

  -- label view (same pattern: only join fish if it exists)
  if has_fish then
    execute $v$
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
        null::text        as transgene_pretty,
        null::text        as nickname,
        null::text        as line_building_stage,
        null::date        as date_birth,
        null::text        as batch_label,
        null::text        as created_by_enriched,
        null::timestamptz as last_plasmid_injection_at,
        null::text        as plasmid_injections_text,
        null::timestamptz as last_rna_injection_at,
        null::text        as rna_injections_text
      from public.v_fish_overview v
    $v$;
  else
    execute $v$
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
        null::text        as transgene_pretty,
        null::text        as nickname,
        null::text        as line_building_stage,
        null::date        as date_birth,
        null::text        as batch_label,
        null::text        as created_by_enriched,
        null::timestamptz as last_plasmid_injection_at,
        null::text        as plasmid_injections_text,
        null::timestamptz as last_rna_injection_at,
        null::text        as rna_injections_text
      from public.v_fish_overview v
    $v$;
  end if;
end$$;

commit;
