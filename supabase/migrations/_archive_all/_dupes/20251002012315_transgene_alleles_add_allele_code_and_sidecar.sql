-- Add allele_code to the canonical table (optional short label)
ALTER TABLE public.transgene_alleles
ADD COLUMN IF NOT EXISTS allele_code text;

-- Unique per base (normalized), only when present
CREATE UNIQUE INDEX IF NOT EXISTS ux_transgene_alleles_base_code_norm
ON public.transgene_alleles (transgene_base_code, lower(btrim(allele_code)))
WHERE allele_code IS NOT NULL AND btrim(allele_code) <> '';

-- Backfill allele_code from allele_name if empty
UPDATE public.transgene_alleles
SET allele_code = nullif(btrim(allele_name), '')
WHERE
    (allele_code IS NULL OR btrim(allele_code) = '')
    AND allele_name IS NOT NULL;

-- Sidecar: keep the human label
ALTER TABLE public.seed_last_upload_links
ADD COLUMN IF NOT EXISTS allele_code text;
