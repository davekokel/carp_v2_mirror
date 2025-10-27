do $$
begin
  if to_regclass('public.v_fish_rich') is null then
    create view public.v_fish_rich as
    select
      f.fish_code::text as fish_code,
      null::text        as genotype_text
    from public.fish f;
  end if;
end$$;
