BEGIN;

-- 1) Recreate well_label as A01, A02 (2-digit zero-padded col)
--    Drop dependent index automatically; we'll recreate it after.
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='plate_slots' AND column_name='well_label'
  ) THEN
    ALTER TABLE public.plate_slots DROP COLUMN well_label;
  END IF;
END$$;

ALTER TABLE public.plate_slots
  ADD COLUMN well_label text
  GENERATED ALWAYS AS (public.row_letter(row_idx) || lpad(col_idx::text, 2, '0')) STORED;

-- Recreate a helpful index on (plate_id, well_label)
CREATE INDEX IF NOT EXISTS ix_plate_slots_label
  ON public.plate_slots(plate_id, well_label);

-- 2) Enforce allowed orientations (or NULL)
ALTER TABLE public.plate_slots
  DROP CONSTRAINT IF EXISTS ck_plate_slots_orientation;

ALTER TABLE public.plate_slots
  ADD CONSTRAINT ck_plate_slots_orientation
  CHECK (
    orientation IS NULL OR orientation IN (
      'dorsal_head_top',
      'lateral_head_left',
      'lateral_head_right',
      'head_down_dorsal_top'
    )
  );

-- 3) Update view to reflect A01/A02 labels (no schema change, but make sure it still selects well_label)
DROP VIEW IF EXISTS public.v_plate_layout;
CREATE VIEW public.v_plate_layout AS
SELECT
  p.plate_code,
  p.plate_name,
  p.format_code,
  pf.n_rows,
  pf.n_cols,
  s.row_idx,
  s.col_idx,
  public.row_letter(s.row_idx) AS row_letter,
  s.well_label,                           -- now like 'A01'
  s.treated_clutch_id,
  COALESCE(tc.treated_clutch_code,'') AS treated_clutch_code,
  s.fish_code,
  COALESCE(s.orientation,'') AS orientation,
  s.created_at
FROM public.plate_slots s
JOIN public.plates        p  ON p.id = s.plate_id
JOIN public.plate_formats pf ON pf.code = p.format_code
LEFT JOIN public.treated_clutches tc ON tc.id = s.treated_clutch_id
ORDER BY p.plate_code, s.row_idx, s.col_idx;

COMMIT;
