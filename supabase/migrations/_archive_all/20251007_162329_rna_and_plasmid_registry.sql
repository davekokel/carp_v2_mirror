BEGIN;

-- RNA registry
CREATE TABLE IF NOT EXISTS public.rna_registry (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    rna_code text UNIQUE NOT NULL,
    rna_nickname text NULL,
    vendor text NULL,
    lot_number text NULL,
    notes text NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    created_by text NULL
);

-- Plasmid registry
CREATE TABLE IF NOT EXISTS public.plasmid_registry (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    plasmid_code text UNIQUE NOT NULL,
    plasmid_nickname text NULL,
    backbone text NULL,
    insert_desc text NULL,
    vendor text NULL,
    lot_number text NULL,
    notes text NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    created_by text NULL
);

-- Helpful indexes
CREATE INDEX IF NOT EXISTS idx_rna_registry_code ON public.rna_registry (rna_code);
CREATE INDEX IF NOT EXISTS idx_plasmid_registry_code ON public.plasmid_registry (plasmid_code);

COMMIT;
