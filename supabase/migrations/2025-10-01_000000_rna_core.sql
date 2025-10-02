-- RNAs master
create table if not exists public.rnas (
  id_uuid      uuid primary key default gen_random_uuid(),
  rna_code     text unique,
  name         text,
  created_at   timestamptz not null default now(),
  created_by   text
);

create unique index if not exists uq_rnas_name_ci on public.rnas (lower(name)) where name is not null;

-- Fish ↔ RNA (id-based, mirrors fish_plasmids)
create table if not exists public.fish_rnas(
  fish_id uuid not null references public.fish(id) on delete cascade,
  rna_id  uuid not null references public.rnas(id_uuid) on delete restrict,
  primary key (fish_id, rna_id)
);

create index if not exists idx_fish_rnas_rna_id on public.fish_rnas(rna_id);

-- Optional: RNA treatments (simple, id-based)
-- Minimal columns now; extend later as your lab needs
create table if not exists public.injected_rna_treatments(
  id_uuid    uuid primary key default gen_random_uuid(),
  fish_id    uuid not null references public.fish(id) on delete cascade,
  rna_id     uuid not null references public.rnas(id_uuid) on delete restrict,
  amount     numeric,
  units      text,
  at_time    timestamptz,
  note       text
);

-- De-dup guard for “same” treatment; adjust as needed
create unique index if not exists uq_rna_txn_dedupe
on public.injected_rna_treatments(fish_id, rna_id, coalesce(at_time, 'epoch'::timestamptz),
                                  coalesce(amount, 0), coalesce(units, ''), coalesce(note, ''));