create schema if not exists staging;

do $$
declare t text;
begin
  foreach t in array array[
    '_dye_csv','_dye_treatments_raw','_plasmid_csv','_plasmid_treatments_raw',
    '_rna_csv','_rna_treatments_raw',
    'fish_csv','fish_links_has_transgenes_csv',
    'fish_links_has_treatment_dye_csv','fish_links_has_treatment_injected_plasmid_csv',
    'fish_links_has_treatment_injected_rna_csv',
    'treatments_unified_raw','_rnas_raw','_plasmids_raw','transgenes_raw'
  ] loop
    if exists (select 1 from pg_class c join pg_namespace n on n.oid=c.relnamespace
               where n.nspname='public' and c.relname=t and c.relkind='r') then
      execute format('alter table public.%I set schema staging', t);
    end if;
  end loop;
end$$;
