BEGIN;

create or replace function public.upsert_fish_by_identity(
  p_seed_batch_id  text,
  p_identity_key   text,
  p_dob            date,
  p_name_human     text,
  p_bg             text,
  p_nick           text,
  p_stage          text,
  p_desc           text,
  p_notes          text,
  p_by             text
) returns table (fish_uuid uuid, fish_code text)
language plpgsql
as $$
declare
  r record;
begin
  -- 1) try to find existing by (batch, identity, dob)
  select f.fish_uuid, f.fish_code
    into r
  from public.fish f
  where f.seed_batch_id = p_seed_batch_id
    and f.name          = p_identity_key
    and f.date_birth    = p_dob
  limit 1;

  -- 2) insert if missing
  if r.fish_uuid is null then
    insert into public.fish (
      seed_batch_id, name, fish_name, date_birth,
      genetic_background, line_building_stage, nickname,
      description, notes, created_by
    )
    values (
      p_seed_batch_id,
      p_identity_key,
      nullif(p_name_human,''),
      p_dob,
      nullif(p_bg,''),
      nullif(p_stage,''),
      nullif(p_nick,''),
      nullif(p_desc,''),
      nullif(p_notes,''),
      nullif(p_by,'')
    );

    -- 3) re-select the row we just inserted (no RETURNING → no ambiguity)
    select f.fish_uuid, f.fish_code
      into r
    from public.fish f
    where f.seed_batch_id = p_seed_batch_id
      and f.name          = p_identity_key
      and f.date_birth    = p_dob
    limit 1;
  else
    -- 4) update if it already existed
    update public.fish
       set fish_name           = coalesce(nullif(p_name_human,''), fish_name),
           genetic_background  = coalesce(nullif(p_bg,''), genetic_background),
           line_building_stage = coalesce(nullif(p_stage,''), line_building_stage),
           nickname            = coalesce(nullif(p_nick,''), nickname),
           description         = coalesce(nullif(p_desc,''), description),
           notes               = coalesce(nullif(p_notes,''), notes)
     where fish_uuid = r.fish_uuid;
  end if;

  return query
  select r.fish_uuid, r.fish_code;
end
$$;

COMMIT;
