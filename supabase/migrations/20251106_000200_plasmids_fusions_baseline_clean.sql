BEGIN;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- plasmids: simple natural key "code" + id
CREATE TABLE IF NOT EXISTS public.plasmids (
  id   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code text UNIQUE NOT NULL,
  name text,
  created_at timestamptz DEFAULT now()
);

-- fusions: fluor + tag; allow tag-only (fluor_id nullable)
CREATE TABLE IF NOT EXISTS public.fusions (
  id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  fluor_id  uuid NULL,
  tag_id    uuid NOT NULL,
  created_at timestamptz DEFAULT now()
);

-- indexes/FKs for fusions
CREATE INDEX IF NOT EXISTS idx_fusions_fluor_id ON public.fusions(fluor_id);
CREATE INDEX IF NOT EXISTS idx_fusions_tag_id   ON public.fusions(tag_id);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='public.fusions'::regclass
      AND conname='fk_fusions_fluor_id__fluors_id'
  ) THEN
    ALTER TABLE public.fusions
      ADD CONSTRAINT fk_fusions_fluor_id__fluors_id
      FOREIGN KEY (fluor_id) REFERENCES public.fluors(id)
      DEFERRABLE INITIALLY DEFERRED NOT VALID;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='public.fusions'::regclass
      AND conname='fk_fusions_tag_id__tags_id'
  ) THEN
    ALTER TABLE public.fusions
      ADD CONSTRAINT fk_fusions_tag_id__tags_id
      FOREIGN KEY (tag_id) REFERENCES public.tags(id)
      DEFERRABLE INITIALLY DEFERRED NOT VALID;
  END IF;
END$$;

-- unique pairing so we can resolve/create by (fluor, tag)
CREATE UNIQUE INDEX IF NOT EXISTS uq_fusions_fluor_tag
  ON public.fusions((fluor_id), tag_id);

-- join_plasmid_fusions (ID-first)
CREATE TABLE IF NOT EXISTS public.join_plasmid_fusions (
  plasmid_id uuid NOT NULL,
  fusion_id  uuid NOT NULL,
  created_at timestamptz DEFAULT now(),
  PRIMARY KEY (plasmid_id, fusion_id)
);

CREATE INDEX IF NOT EXISTS idx_jpf_plasmid_id ON public.join_plasmid_fusions(plasmid_id);
CREATE INDEX IF NOT EXISTS idx_jpf_fusion_id  ON public.join_plasmid_fusions(fusion_id);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='public.join_plasmid_fusions'::regclass
      AND conname='fk_jpf_plasmid_id__plasmids_id'
  ) THEN
    ALTER TABLE public.join_plasmid_fusions
      ADD CONSTRAINT fk_jpf_plasmid_id__plasmids_id
      FOREIGN KEY (plasmid_id) REFERENCES public.plasmids(id)
      DEFERRABLE INITIALLY DEFERRED NOT VALID;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='public.join_plasmid_fusions'::regclass
      AND conname='fk_jpf_fusion_id__fusions_id'
  ) THEN
    ALTER TABLE public.join_plasmid_fusions
      ADD CONSTRAINT fk_jpf_fusion_id__fusions_id
      FOREIGN KEY (fusion_id) REFERENCES public.fusions(id)
      DEFERRABLE INITIALLY DEFERRED NOT VALID;
  END IF;
END$$;

COMMIT;
