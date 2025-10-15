begin;

create extension if not exists pgcrypto;
DO 28762
declare
  fish_pk_col text := case
    when exists (
      select 1 from information_schema.columns
       where table_schema='public' and table_name='fish' and column_name='id'
    ) then 'id' else 'id_uuid' end;

  plasmid_pk_col text := case
    when exists (
      select 1 from information_schema.columns
       where table_schema='public' and table_name='plasmids' and column_name='id'
    ) then 'id' else 'id_uuid' end;
begin
  if to_regclass('public.fish') is null or to_regclass('public.plasmids') is null then
    raise notice 'Skipping injected_plasmid_treatments: missing fish/plasmids deps.';
    return;
  end if;

  if to_regclass('public.injected_plasmid_treatments') is null then
    execute format($f$
      create table public.injected_plasmid_treatments (
        id uuid primary key default gen_random_uuid(),
        fish_id uuid not null,
        plasmid_id uuid not null,
        amount numeric null,
        units text null,
        at_time timestamptz null,
        note text null
      );
    $f$);

    execute format(
      'alter table public.injected_plasmid_treatments
         add constraint fk_ipt_fish
         foreign key (fish_id) references public.fish(%I) on delete cascade',
      fish_pk_col
    );

    execute format(
      'alter table public.injected_plasmid_treatments
         add constraint fk_ipt_plasmid
         foreign key (plasmid_id) references public.plasmids(%I) on delete restrict',
      plasmid_pk_col
    );

    create unique index if not exists uq_ipt_natural
      on public.injected_plasmid_treatments (fish_id, plasmid_id, at_time, amount, units, note);
  else
    if not exists (
      select 1 from pg_constraint where conname='fk_ipt_fish'
    ) then
      execute format(
        'alter table public.injected_plasmid_treatments
           add constraint fk_ipt_fish
           foreign key (fish_id) references public.fish(%I) on delete cascade',
        fish_pk_col
      );
    end if;

    if not exists (
      select 1 from pg_constraint where conname='fk_ipt_plasmid'
    ) then
      execute format(
        'alter table public.injected_plasmid_treatments
           add constraint fk_ipt_plasmid
           foreign key (plasmid_id) references public.plasmids(%I) on delete restrict',
        plasmid_pk_col
      );
    end if;

    create unique index if not exists uq_ipt_natural
      on public.injected_plasmid_treatments (fish_id, plasmid_id, at_time, amount, units, note);
  end if;
end $$;

commit;
