-- migrations/2025-10-01_plasmid_treatments.sql

create table if not exists public.injected_plasmid_treatments (
  id            uuid primary key default gen_random_uuid(),
  fish_id       uuid not null references public.fish(id) on delete cascade,
  plasmid_id    uuid not null references public.plasmids(id_uuid) on delete restrict,
  amount        numeric null,
  units         text    null,
  at_time       timestamptz null,
  note          text    null
);

-- de-dupe policy: one row per (fish, plasmid, time, amount, units, note)
-- tweak to your taste (e.g., drop amount/units/note if you want looser uniqueness)
create unique index if not exists uq_ipt_natural
  on public.injected_plasmid_treatments(fish_id, plasmid_id, at_time, amount, units, note);