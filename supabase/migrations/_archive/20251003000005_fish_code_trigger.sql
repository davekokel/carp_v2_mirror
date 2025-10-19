begin;

create sequence if not exists public.fish_code_seq;

create or replace function public.fish_code_next()
returns text language plpgsql as $$
declare
  n bigint;
begin
  select nextval('public.fish_code_seq') into n;
  return 'F' || to_char(now(),'YYYYMMDD') || '-' || lpad(n::text,4,'0');
end
$$;

-- Only add fish_code if the column exists (or skip if you don't use it);
do $$
begin
  if exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='fish' and column_name='fish_code'
  ) then
    if not exists (
      select 1 from pg_constraint c
      join pg_class t on t.oid=c.conrelid
      join pg_namespace n on n.oid=t.relnamespace
      where c.contype='u' and n.nspname='public' and t.relname='fish' and c.conname='uq_fish_fish_code'
    ) then
      alter table public.fish
        add constraint uq_fish_fish_code unique (fish_code);
    end if;
  end if;
end $$;

create or replace function public.trg_fish_set_code()
returns trigger language plpgsql as $$
begin
  if new.fish_code is null then
    new.fish_code := public.fish_code_next();
  end if;
  return new;
end
$$;
do $$
begin
  if exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='fish' and column_name='fish_code'
  ) then
    if not exists (
      select 1 from pg_trigger
      where tgname='before_insert_set_fish_code'
    ) then
      create trigger before_insert_set_fish_code
      before insert on public.fish
      for each row execute function public.trg_fish_set_code();
    end if;
  else
    raise notice 'Skipping fish_code trigger: public.fish.fish_code not found.';
  end if;
end $$;

commit;
