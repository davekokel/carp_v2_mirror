BEGIN;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Minimal injected_plasmid_treatments (later migrations will add columns like fish_id)
CREATE TABLE IF NOT EXISTS public.injected_plasmid_treatments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    plasmid_id text,
    amount numeric,
    units text,
    at_time timestamptz,
    note text,
    created_at timestamptz NOT NULL DEFAULT now(),
    created_by text
);

-- Minimal injected_rna_treatments (later migrations add/alter columns as needed)
CREATE TABLE IF NOT EXISTS public.injected_rna_treatments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    rna_id text,
    amount numeric,
    units text,
    at_time timestamptz,
    note text,
    created_at timestamptz NOT NULL DEFAULT now(),
    created_by text
);
COMMIT;
