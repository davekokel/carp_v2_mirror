BEGIN;

CREATE TABLE IF NOT EXISTS public.legacy_roi_genotype_constructs_v5 (
  roi_path TEXT NOT NULL,
  construct_base_code TEXT NOT NULL,
  allele_code TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (roi_path, construct_base_code, allele_code)
);

CREATE TABLE IF NOT EXISTS public.legacy_roi_treatment_constructs_v5 (
  roi_path TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('rna','plasmid')),
  construct_base_code TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (roi_path, kind, construct_base_code)
);

COMMIT;
