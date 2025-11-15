BEGIN;

-- Remove ROI-only table if it exists
DROP TABLE IF EXISTS public.roi_notes CASCADE;

-- Ensure annotations table exists with at least an id column
CREATE TABLE IF NOT EXISTS public.annotations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid()
);

-- Bring annotations into the polymorphic shape (add columns if missing)
ALTER TABLE public.annotations
  ADD COLUMN IF NOT EXISTS entity_kind text,
  ADD COLUMN IF NOT EXISTS entity_id uuid,
  ADD COLUMN IF NOT EXISTS note_text text,
  ADD COLUMN IF NOT EXISTS created_by text,
  ADD COLUMN IF NOT EXISTS created_at timestamptz DEFAULT now();

-- Backfill created_at for any existing rows that might be NULL
UPDATE public.annotations
SET created_at = now()
WHERE created_at IS NULL;

-- Create the composite index if it isn't already present
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_indexes
    WHERE schemaname = 'public'
      AND tablename = 'annotations'
      AND indexname = 'idx_annotations_entity'
  ) THEN
    CREATE INDEX idx_annotations_entity
      ON public.annotations(entity_kind, entity_id);
  END IF;
END$$;

COMMIT;
