BEGIN;
DROP VIEW IF EXISTS public.v_plate_layout CASCADE;
CREATE VIEW public.v_plate_layout AS
WITH fmt AS (
  SELECT p.id AS plate_id, pf.code AS format_code, pf.n_rows, pf.n_cols,
         p.plate_code, p.nickname
  FROM public.plates p
  LEFT JOIN public.plate_formats pf ON pf.code = p.format_code
)
SELECT
  f.plate_code,
  f.nickname                              AS plate_nickname,
  f.format_code,
  f.n_rows,
  f.n_cols,
  s.row_idx,
  s.col_idx,
  chr(64+s.row_idx)::text                 AS row_letter,             -- A..X
  (chr(64+s.row_idx)||lpad(s.col_idx::text,2,'0'))::text AS well_label, -- A01
  s.treated_clutch_id,
  tc.treated_clutch_code,
  s.orientation,
  s.created_at
FROM public.plate_slots s
JOIN fmt f ON f.plate_id = s.plate_id
LEFT JOIN public.treated_clutches tc ON tc.id = s.treated_clutch_id
ORDER BY f.plate_code, s.row_idx, s.col_idx;
COMMIT;
