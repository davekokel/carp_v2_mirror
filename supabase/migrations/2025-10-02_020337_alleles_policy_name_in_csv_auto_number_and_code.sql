-- Sidecar: keep the human label as allele_name (and optionally allele_code if you want to show a custom code)
ALTER TABLE public.seed_last_upload_links
  ADD COLUMN IF NOT EXISTS allele_name  text,
  ADD COLUMN IF NOT EXISTS allele_code  text;

-- Helper: derive a short code prefix from a base (letters only, lowercased, trailing digits stripped)
CREATE OR REPLACE FUNCTION public.code_prefix(p_base text)
RETURNS text LANGUAGE sql IMMUTABLE STRICT AS $$
  SELECT lower(regexp_replace(btrim($1), '[^A-Za-z]+$',''))  -- letters at the front
$$;

-- Reseed canonical alleles for all bases present in sidecar:
--   * allele_name  := human label from CSV
--   * allele_number := ROW_NUMBER() per base (1..N)
--   * allele_code  := code_prefix(base) || '-' || allele_number
CREATE OR REPLACE FUNCTION public.reseed_bases_from_sidecar_names()
RETURNS void LANGUAGE plpgsql AS $$
BEGIN
  -- bases we need to reseed, scoped to current sidecar contents
  CREATE TEMP TABLE _bases ON COMMIT DROP AS
  SELECT DISTINCT slul.transgene_base_code AS base
  FROM public.seed_last_upload_links slul
  WHERE slul.transgene_base_code IS NOT NULL AND btrim(slul.transgene_base_code) <> '';

  -- wipe normalized links/allele defs for those bases (FK-safe)
  DELETE FROM public.fish_transgene_alleles fta
  USING _bases b
  WHERE fta.transgene_base_code = b.base;

  DELETE FROM public.transgene_alleles ta
  USING _bases b
  WHERE ta.transgene_base_code = b.base;

  -- collect distinct allele_name labels per base (non-empty)
  CREATE TEMP TABLE _ordered ON COMMIT DROP AS
  SELECT
    slul.transgene_base_code                                     AS base,
    NULLIF(btrim(slul.allele_name), '')                          AS allele_name,
    ROW_NUMBER() OVER (PARTITION BY slul.transgene_base_code
                       ORDER BY lower(NULLIF(btrim(slul.allele_name), ''))) AS allele_number
  FROM (
    SELECT DISTINCT transgene_base_code, allele_name
    FROM public.seed_last_upload_links
    WHERE transgene_base_code IS NOT NULL AND btrim(transgene_base_code) <> ''
  ) slul
  WHERE slul.allele_name IS NOT NULL;

  -- seed canonical 1..N with auto code = prefix-number
  INSERT INTO public.transgene_alleles (transgene_base_code, allele_number, allele_code, allele_name)
  SELECT
    o.base,
    o.allele_number,
    public.code_prefix(o.base) || '-' || o.allele_number::text,
    o.allele_name
  FROM _ordered o
  ORDER BY o.base, o.allele_number;
END$$;

-- View stays as-is structurally; it will pick up canonical + sidecar.
