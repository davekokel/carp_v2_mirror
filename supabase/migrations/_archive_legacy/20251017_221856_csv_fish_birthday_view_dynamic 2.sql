-- Robust CSV import view:
-- - Uses 'birthday' (canonical) for CSV.
-- - Never references non-existent columns in SELECT (uses row_to_json for optional fields).
-- - Creates INSERT/UPDATE rules dynamically: include genetic_background only if the column exists.

-- Drop any prior version (idempotent)
drop view if exists public.fish_csv cascade;

-- Create a read view that is resilient even if fish lacks some text columns
create view public.fish_csv as
select
    f.fish_code,
    f.birthday,
    f.created_at,
    coalesce(row_to_json(f.f)::jsonb ->> 'name', '') as name,
    coalesce(row_to_json(f.f)::jsonb ->> 'nickname', '') as nickname,
    coalesce(row_to_json(f.f)::jsonb ->> 'genetic_background', '') as genetic_background,
    coalesce(row_to_json(f.f)::jsonb ->> 'created_by', '') as created_by
from public.fish AS f;

comment on view public.fish_csv is
'Writable CSV import view: accepts columns (fish_code, name, nickname, genetic_background?, birthday, created_by). birthday maps to fish.birthday.';

-- Create INSERT/UPDATE rules depending on the presence of fish.genetic_background
do $$
declare has_bg boolean;
begin
  select exists(
    select 1 from information_schema.columns  where table_schema='public' and table_name='fish' and column_name='genetic_background'
  ) into has_bg;

  if has_bg then
    -- With genetic_background column
    execute $SQL$
      create or replace rule fish_csv_insert as
      on insert to public.fish_csv do instead
      insert into public.fish (fish_code, name, nickname, genetic_background, birthday, created_by)
      values (
        coalesce(new.fish_code, ''),
        coalesce(new.name, ''),
        coalesce(new.nickname, ''),
        coalesce(new.genetic_background, ''),
        new.birthday,
        coalesce(new.created_by, '')
      )
      on conflict (fish_code) do update set
        name               = excluded.name,
        nickname           = excluded.nickname,
        genetic_background = excluded.genetic_background,
        birthday           = excluded.birthday,
        created_by         = excluded.created_by;
    $SQL$;

    execute $SQL$
      create or replace rule fish_csv_update as
      on update to public.fish_csv do instead
      update public.fish set
        name               = coalesce(new.name, public.fish.name),
        nickname           = coalesce(new.nickname, public.fish.nickname),
        genetic_background = coalesce(new.genetic_background, public.fish.genetic_background),
        birthday           = coalesce(new.birthday, public.fish.birthday),
        created_by         = coalesce(new.created_by, public.fish.created_by)
      where public.fish.fish_code = new.fish_code;
    $SQL$;

  else
    -- Without genetic_background column
    execute $SQL$
      create or replace rule fish_csv_insert as
      on insert to public.fish_csv do instead
      insert into public.fish (fish_code, name, nickname, birthday, created_by)
      values (
        coalesce(new.fish_code, ''),
        coalesce(new.name, ''),
        coalesce(new.nickname, ''),
        new.birthday,
        coalesce(new.created_by, '')
      )
      on conflict (fish_code) do update set
        name               = excluded.name,
        nickname           = excluded.nickname,
        birthday           = excluded.birthday,
        created_by         = excluded.created_by;
    $SQL$;

    execute $SQL$
      create or replace rule fish_csv_update as
      on update to public.fish_csv do instead
      update public.fish set
        name               = coalesce(new.name, public.fish.name),
        nickname           = coalesce(new.nickname, public.fish.nickname),
        birthday           = coalesce(new.birthday, public.fish.birthday),
        created_by         = coalesce(new.created_by, public.fish.created_by)
      where public.fish.fish_code = new.fish_code;
    $SQL$;
  end if;
end$$;
