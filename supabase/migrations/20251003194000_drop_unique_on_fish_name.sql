begin;

do $$
begin
  if exists (
    select 1
    from pg_constraint
    where conrelid = 'public.fish'::regclass
      and contype  = 'u'
      and conname  = 'fish_name_key'
  ) then
    alter table public.fish drop constraint fish_name_key;
  end if;
end $$;

create unique index if not exists uq_fish_code on public.fish(fish_code);
create index if not exists ix_fish_name on public.fish(name);

commit;
