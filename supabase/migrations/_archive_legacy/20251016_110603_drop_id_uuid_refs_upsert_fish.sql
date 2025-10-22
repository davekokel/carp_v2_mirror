begin;

create or replace function public.upsert_fish_by_batch_name_dob(
    p_seed_batch_id text,
    p_name text,
    p_date_birth date,
    p_genetic_background text,
    p_nickname text,
    p_line_building_stage text,
    p_description text,
    p_notes text,
    p_created_by text
) returns table (id uuid, fish_code text)
language plpgsql
as $$
declare
  v_id   uuid;
  v_code text;
begin
  -- try existing (batch, name, dob)
  select f.id, f.fish_code
    into v_id, v_code
  from public.fish AS f
  join public.fish_seed_batches_map AS m
    on m.fish_id = f.id
   and m.seed_batch_id = p_seed_batch_id
  where f.name = p_name
    and f.date_birth = p_date_birth
  limit 1;

  if v_id is not null then
    update public.fish
       set genetic_background = coalesce(p_genetic_background, genetic_background),
           nickname           = coalesce(p_nickname, nickname),
           line_building_stage= coalesce(p_line_building_stage, line_building_stage),
           description        = coalesce(p_description, description),
           notes              = coalesce(p_notes, notes),
           created_by         = coalesce(p_created_by, created_by)
     where id = v_id;

    return query select v_id, v_code;
    return;
  end if;

  -- create new fish
  insert into public.fish(
    name, date_birth, genetic_background, nickname,
    line_building_stage, description, notes, created_by
  )
  values (
    p_name, p_date_birth, p_genetic_background, p_nickname,
    p_line_building_stage, p_description, p_notes, p_created_by
  )
  returning id, public.fish.fish_code into v_id, v_code;

  -- map to batch (idempotent)
  insert into public.fish_seed_batches_map(fish_id, batch_label, seed_batch_id)
  values (v_id, null, p_seed_batch_id)
  on conflict (fish_id, seed_batch_id) do nothing;

  return query select v_id, v_code;
end;
$$;

commit;
