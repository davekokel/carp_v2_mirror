BEGIN;

CREATE TABLE public.clutch_selection_events_v11 (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  clutch_id          uuid NOT NULL REFERENCES public.clutches(id) ON DELETE CASCADE,
  treated_clutch_id  uuid REFERENCES public.treated_clutches_v11(id) ON DELETE CASCADE,
  selection_kind     text NOT NULL,
  selection_label    text,
  notes              text,
  created_at         timestamptz NOT NULL DEFAULT now(),
  created_by         text
);

CREATE INDEX IF NOT EXISTS idx_clutch_selection_events_v11_clutch_id
  ON public.clutch_selection_events_v11 (clutch_id);

CREATE INDEX IF NOT EXISTS idx_clutch_selection_events_v11_treated_clutch_id
  ON public.clutch_selection_events_v11 (treated_clutch_id);

COMMENT ON TABLE public.clutch_selection_events_v11 IS
'Selection events over clutches or treated clutches (e.g. phenotype-based narrowing, nursery intake, imaging subset). Each row records who/when/why a subset of a clutch was selected.';

CREATE TABLE public.clutch_selection_genotypes_v11 (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  selection_event_id uuid NOT NULL REFERENCES public.clutch_selection_events_v11(id) ON DELETE CASCADE,
  clutch_genotype_id uuid NOT NULL REFERENCES public.clutch_genotypes_v11(id) ON DELETE CASCADE,
  is_primary         boolean NOT NULL DEFAULT false,
  created_at         timestamptz NOT NULL DEFAULT now(),
  created_by         text
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_clutch_selection_genotypes_v11_unique
  ON public.clutch_selection_genotypes_v11 (selection_event_id, clutch_genotype_id);

CREATE INDEX IF NOT EXISTS idx_clutch_selection_genotypes_v11_event
  ON public.clutch_selection_genotypes_v11 (selection_event_id);

CREATE INDEX IF NOT EXISTS idx_clutch_selection_genotypes_v11_genotype
  ON public.clutch_selection_genotypes_v11 (clutch_genotype_id);

COMMENT ON TABLE public.clutch_selection_genotypes_v11 IS
'Links selection events to expected clutch genotypes (clutch_genotypes_v11). A selection can keep one or more expected genotypes ''in play'' and optionally mark one as primary.';

COMMIT;
