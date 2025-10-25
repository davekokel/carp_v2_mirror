begin;

create extension if not exists pgcrypto;

-- 1) Base table: one row per plasmid
create table if not exists public.plasmids (
  id                   uuid primary key default gen_random_uuid(),
  code                 text unique not null,          -- human code, e.g. PL-000123
  name                 text,
  nickname             text,
  fluors               text,                           -- free text list (',' or ';' separated)
  resistance           text,                           -- e.g. amp/kan/chlor
  supports_invitro_rna boolean not null default false,
  notes                text,
  created_by           text,
  created_at           timestamptz not null default now()
);
create index if not exists plasmids_code_idx on public.plasmids (code);
create index if not exists plasmids_created_idx on public.plasmids (created_at desc);

-- 2) Optional child: RNA per plasmid (0..1 for now; can relax later)
create table if not exists public.rnas (
  id          uuid primary key default gen_random_uuid(),
  plasmid_id  uuid not null references public.plasmids(id) on delete cascade,
  code        text unique,           -- RNA code if you want a human code
  name        text,
  notes       text,
  created_by  text,
  created_at  timestamptz not null default now()
);
create index if not exists rnas_plasmid_idx on public.rnas (plasmid_id);

-- 3) Canonical read view (fixed shape your page can rely on)
create or replace view public.v_plasmids as
select
  p.id,
  p.code,
  p.name,
  p.nickname,
  p.fluors,
  p.resistance,
  p.supports_invitro_rna,
  p.created_by,
  p.notes,
  p.created_at,
  r.id   as rna_id,
  r.code as rna_code,
  r.name as rna_name
from public.plasmids p
left join public.rnas r on r.plasmid_id = p.id;

comment on view public.v_plasmids is 'Unified plasmid view with optional RNA fields (rna_id, rna_code, rna_name).';

-- 4) Action: ensure RNA for a plasmid (idempotent by code)
create or replace function public.ensure_rna_for_plasmid(
  plasmid_code text,
  rna_code_prefix text,
  rna_name_in text,
  by_in text,
  notes_in text
)
returns table (rna_id uuid, rna_code text) language plpgsql as $$
declare
  v_pid uuid;
  v_rna_id uuid;
  v_rna_code text;
begin
  select id into v_pid from public.plasmids where code = plasmid_code limit 1;
  if v_pid is null then
    raise exception 'plasmid % not found', plasmid_code;
  end if;

  -- if RNA already exists, return it
  select id, coalesce(code, '') into v_rna_id, v_rna_code
  from public.rnas where plasmid_id = v_pid limit 1;

  if v_rna_id is null then
    v_rna_code := nullif(trim(rna_code_prefix), '');
    if v_rna_code is not null then
      -- make RNA code unique-ish: PREFIX-<plasmid-code>
      v_rna_code := v_rna_code || '-' || plasmid_code;
    end if;

    insert into public.rnas (plasmid_id, code, name, notes, created_by)
    values (v_pid, v_rna_code, nullif(trim(rna_name_in), ''), notes_in, by_in)
    returning id, code into v_rna_id, v_rna_code;
  end if;

  return query select v_rna_id, v_rna_code;
end $$;

commit;
