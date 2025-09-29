do $$
begin
  -- Conditionally grant on each relation so resets never fail if some are absent
  if to_regclass('public.fish') is not null then
    execute 'grant select on public.fish to anon, authenticated';
  end if;

  if to_regclass('public.transgenes') is not null then
    execute 'grant select on public.transgenes to anon, authenticated';
  end if;

  if to_regclass('public.fish_transgene_alleles') is not null then
    execute 'grant select on public.fish_transgene_alleles to anon, authenticated';
  end if;

  if to_regclass('public.treatments') is not null then
    execute 'grant select on public.treatments to anon, authenticated';
  end if;

  if to_regclass('public.fish_treatments') is not null then
    execute 'grant select on public.fish_treatments to anon, authenticated';
  end if;

  if to_regclass('public.tank_assignments') is not null then
    execute 'grant select on public.tank_assignments to anon, authenticated';
  end if;

  if to_regclass('public.transgene_allele_catalog') is not null then
    execute 'grant select on public.transgene_allele_catalog to anon, authenticated';
  end if;
end$$;
