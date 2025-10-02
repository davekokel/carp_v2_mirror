-- Upsert seed mapping whenever a log row is written with (fish_id, seed_batch_id)
create or replace function public.tg_upsert_fish_seed_maps() returns trigger as $$
begin
  if new.seed_batch_id is not null and new.fish_id is not null then
    -- 1) Ensure seed_batches has a row (label defaults to id; you can prettify later)
    insert into public.seed_batches(seed_batch_id, batch_label)
    values (new.seed_batch_id, new.seed_batch_id)
    on conflict (seed_batch_id) do nothing;

    -- 2) Tie this fish to the batch id (latest wins)
    insert into public.fish_seed_batches(fish_id, seed_batch_id, updated_at)
    values (new.fish_id, new.seed_batch_id, now())
    on conflict (fish_id) do update
      set seed_batch_id = excluded.seed_batch_id,
          updated_at    = excluded.updated_at;
  end if;
  return new;
end
$$ language plpgsql;

drop trigger if exists trg_upsert_fish_seed_maps on public.load_log_fish;
create trigger trg_upsert_fish_seed_maps
after insert on public.load_log_fish
for each row execute function public.tg_upsert_fish_seed_maps();
