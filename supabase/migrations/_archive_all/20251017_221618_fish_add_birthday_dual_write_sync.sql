-- Add fish.birthday, backfill, and keep it in sync with fish.date_birth.
-- Also keep fish_csv view writable using 'birthday'.

-- 1) Add column if not exists
do $$
begin
  if not exists (
    select 1 from information_schema.columns  where table_schema='public' and table_name='fish' and column_name='birthday'
  ) then
    alter table public.fish add column birthday date;
  end if;
end$$;

-- 2) Backfill birthday from date_birth (non-destructive)
update public.fish
set birthday = coalesce(birthday, date_birth)
where birthday is null;

-- 3) Sync trigger to keep both columns in lockstep during transition
create or replace function public.fish_birthday_sync() returns trigger
language plpgsql as $$
begin
  -- If 'birthday' provided, mirror to date_birth
  if tg_op in ('INSERT', 'UPDATE') then
    if new.birthday is not null and (new.date_birth is distinct from new.birthday) then
      new.date_birth := new.birthday;
    end if;
    -- If only date_birth provided (legacy writers), mirror to birthday
    if new.date_birth is not null and (new.birthday is distinct from new.date_birth) then
      new.birthday := new.date_birth;
    end if;
  end if;
  return new;
end;
$$;

drop trigger if exists trg_fish_birthday_sync on public.fish;
create trigger trg_fish_birthday_sync
before insert or update on public.fish
for each row execute procedure public.fish_birthday_sync();

comment on function public.fish_birthday_sync() is
'Keeps fish.birthday and fish.date_birth in sync during transition to birthday as canonical.';

-- 4) CSV-compatible writable view: expose 'birthday' as the canonical CSV column
drop view if exists public.fish_csv cascade;

create view public.fish_csv as
select
  f.fish_code,
  coalesce(f.name, '')               as name,
  coalesce(f.nickname, '')           as nickname,
  coalesce(f.genotype, '')           as genotype,
  coalesce(f.genetic_background, '') as genetic_background,
  f.birthday,
  coalesce(f.created_by, '')         as created_by,
  f.created_at
from public.fish AS f;

-- INSERT/UPDATE rules mapping 'birthday' to fish.birthday (sync trigger will mirror to date_birth)
create or replace rule fish_csv_insert as
on insert to public.fish_csv do instead
insert into public.fish (fish_code, name, nickname, genotype, genetic_background, birthday, created_by)
values (
  coalesce(new.fish_code, ''),
  coalesce(new.name, ''),
  coalesce(new.nickname, ''),
  coalesce(new.genotype, ''),
  coalesce(new.genetic_background, ''),
  new.birthday,
  coalesce(new.created_by, '')
)
on conflict (fish_code) do update set
  name               = excluded.name,
  nickname           = excluded.nickname,
  genotype           = excluded.genotype,
  genetic_background = excluded.genetic_background,
  birthday           = excluded.birthday,
  created_by         = excluded.created_by;

create or replace rule fish_csv_update as
on update to public.fish_csv do instead
update public.fish set
  name               = coalesce(new.name, public.fish.name),
  nickname           = coalesce(new.nickname, public.fish.nickname),
  genotype           = coalesce(new.genotype, public.fish.genotype),
  genetic_background = coalesce(new.genetic_background, public.fish.genetic_background),
  birthday           = coalesce(new.birthday, public.fish.birthday),
  created_by         = coalesce(new.created_by, public.fish.created_by)
where public.fish.fish_code = new.fish_code;

comment on view public.fish_csv is
'Writable CSV import view: CSV ''birthday'' → fish.birthday; a sync trigger mirrors date_birth during transition.';
