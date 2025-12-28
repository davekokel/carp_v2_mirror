BEGIN;

CREATE TABLE IF NOT EXISTS public.legacy_roi_path_map_v5 (
  roi_path TEXT PRIMARY KEY,

  date_mount_id TEXT,
  genotype_base_codes TEXT,
  genotype_allele_codes TEXT,
  treatment_rna_base_codes TEXT,
  treatment_plasmid_base_codes TEXT,

  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMIT;
