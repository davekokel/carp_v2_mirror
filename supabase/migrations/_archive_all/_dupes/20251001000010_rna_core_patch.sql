-- Bring injected_rna_treatments up to expected shape if it already existed
alter table if exists public.injected_rna_treatments
add column if not exists amount numeric,
add column if not exists units text,
add column if not exists at_time timestamptz,
add column if not exists note text;

-- Recreate the dedupe guard in a way that works regardless of prior state
drop index if exists public.uq_rna_txn_dedupe;

create unique index uq_rna_txn_dedupe
on public.injected_rna_treatments (
    fish_id,
    rna_id,
    coalesce(at_time, 'epoch'::timestamptz),
    coalesce(amount, 0),
    coalesce(units, ''),
    coalesce(note, '')
);
