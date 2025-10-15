begin;
DO 28762
declare
  fish_pk text := util_mig.pk_col('public','fish');
  rna_pk  text := util_mig.pk_col('public','rnas');
begin
  if not util_mig.table_exists('public','fish')
     or not util_mig.table_exists('public','rnas') then
    raise notice 'Skipping injected_rna_treatments: deps missing.';
    return;
  end if;

  if fish_pk is null or rna_pk is null then
    raise notice 'Skipping injected_rna_treatments: could not determine PK columns.';
    return;
  end if;

  if to_regclass('public.injected_rna_treatments') is null then
    execute $sql$
      create table public.injected_rna_treatments (
        id uuid primary key default gen_random_uuid(),
        fish_id uuid not null,
        rna_id uuid not null,
        amount numeric null,
        units text null,
        at_time timestamptz null,
        note text null
      )
    $sql$;
  end if;

  perform util_mig.ensure_fk(
    'public','injected_rna_treatments', array['fish_id'],
    'public','fish', array[fish_pk],
    'fk_irt_fish','cascade'
  );

  perform util_mig.ensure_fk(
    'public','injected_rna_treatments', array['rna_id'],
    'public','rnas', array[rna_pk],
    'fk_irt_rna','restrict'
  );

  perform util_mig.ensure_unique(
    'public','injected_rna_treatments','uq_irt_natural',
    array['fish_id','rna_id','at_time','amount','units','note']
  );
end $$;

commit;
