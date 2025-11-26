BEGIN;

-- 1) Ensure constructs has the plasmid fields
ALTER TABLE public.constructs
  ADD COLUMN IF NOT EXISTS resistance    text,
  ADD COLUMN IF NOT EXISTS backbone      text,
  ADD COLUMN IF NOT EXISTS plasmid_notes text;

-- 2) One-time merge: fill NULLs from construct_plasmids, but don't overwrite existing values
UPDATE public.constructs c
SET
  resistance    = COALESCE(c.resistance,    cp.resistance),
  backbone      = COALESCE(c.backbone,      cp.backbone),
  plasmid_notes = COALESCE(c.plasmid_notes, cp.notes)
FROM public.construct_plasmids cp
WHERE cp.construct_id = c.id;

-- 3) Rebuild v10_constructs_overview to stop depending on construct_plasmids
DROP VIEW IF EXISTS public.v10_constructs_overview;

CREATE VIEW public.v10_constructs_overview AS
SELECT
  c.construct_code,
  c.construct_kind,
  c.construct_name,
  c.resistance,
  c.description,
  c.created_at
FROM public.constructs c;

-- 4) Drop the now-redundant table
DROP TABLE IF EXISTS public.construct_plasmids;

COMMIT;
