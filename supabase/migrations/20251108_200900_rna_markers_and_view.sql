BEGIN;

CREATE TABLE IF NOT EXISTS public.rna_proteins (
  rna_code   text NOT NULL,
  fluor_code text NOT NULL,
  tag_code   text NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT fk_rna_proteins_rna
    FOREIGN KEY (rna_code) REFERENCES public.rnas(rna_code) ON DELETE CASCADE
);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname='public' AND indexname='pk_rna_proteins'
  ) THEN
    CREATE UNIQUE INDEX pk_rna_proteins
      ON public.rna_proteins (rna_code, COALESCE(tag_code,'∅'), fluor_code);
  END IF;
END$$;

DROP VIEW IF EXISTS public.v_rnas;

CREATE VIEW public.v_rnas AS
WITH rp AS (
  SELECT
    rna_code,
    COALESCE(string_agg(DISTINCT fluor_code, ', ' ORDER BY fluor_code), '') AS fluor_names,
    COALESCE(string_agg(DISTINCT COALESCE(tag_code,''), ', ' ORDER BY COALESCE(tag_code,'')), '') AS tag_names
  FROM public.rna_proteins
  GROUP BY rna_code
)
SELECT
  r.id,
  r.rna_code,
  COALESCE(r.rna_name,'')             AS rna_name,
  COALESCE(r.notes,'')                AS notes,
  COALESCE(rp.fluor_names,'')         AS fluor_names,
  COALESCE(NULLIF(rp.tag_names,''),'') AS tag_names,
  r.created_by,
  r.created_at
FROM public.rnas r
LEFT JOIN rp ON rp.rna_code = r.rna_code
ORDER BY r.rna_code;

COMMIT;
