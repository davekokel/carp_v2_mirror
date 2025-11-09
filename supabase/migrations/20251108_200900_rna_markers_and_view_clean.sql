BEGIN;

-- If you want to keep a simple markers table for RNAs, ensure it's here and ID-first.
CREATE TABLE IF NOT EXISTS public.rna_markers (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  rna_id uuid NOT NULL,
  marker_code text NOT NULL,
  created_at timestamptz DEFAULT now()
);

-- Index + FK to rnas
CREATE INDEX IF NOT EXISTS idx_rna_markers_rna_id ON public.rna_markers(rna_id);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='public.rna_markers'::regclass
      AND conname='fk_rna_markers_rna_id__rnas_id'
  ) THEN
    ALTER TABLE public.rna_markers
      ADD CONSTRAINT fk_rna_markers_rna_id__rnas_id
      FOREIGN KEY (rna_id) REFERENCES public.rnas(id)
      DEFERRABLE INITIALLY DEFERRED NOT VALID;
  END IF;
END$$;

-- Recreate the view without rna_name; use rna_code
DROP VIEW IF EXISTS public.v_rna_markers;
CREATE VIEW public.v_rna_markers AS
SELECT
  r.id        AS rna_id,
  r.rna_code  AS rna_code,
  m.marker_code,
  m.created_at
FROM public.rnas r
LEFT JOIN public.rna_markers m
  ON m.rna_id = r.id;

COMMIT;
