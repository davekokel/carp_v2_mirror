begin;

-- Drop the mistaken unique-on-name if present (idempotent);
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

-- Ensure fish_code remains the unique identity (idempotent)
create unique index if not exists uq_fish_code on public.fish (fish_code);

-- Optional: keep name searchable without enforcing uniqueness
create index if not exists ix_fish_name on public.fish (name);

commit;
