BEGIN;

ALTER TABLE public.legacy_parent_to_allele
  ALTER COLUMN plasmid_base_code DROP NOT NULL,
  ALTER COLUMN allele_nickname   DROP NOT NULL;

COMMIT;
