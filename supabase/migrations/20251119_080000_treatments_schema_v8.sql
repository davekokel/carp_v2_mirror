BEGIN;

----------------------------------------------------------------------
-- v8: Treatment schema + fusion integration
----------------------------------------------------------------------

-- 1. treatments
CREATE TABLE IF NOT EXISTS public.treatments (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  treatment_code text UNIQUE NOT NULL,
  category       text,
  name           text,
  description    text,
  notes          text,
  created_at     timestamptz NOT NULL DEFAULT now(),
  created_by     text
);

-- 2. join_clutch_treatments
CREATE TABLE IF NOT EXISTS public.join_clutch_treatments (
  clutch_id    uuid NOT NULL REFERENCES public.clutches(id)
                          ON UPDATE CASCADE ON DELETE CASCADE,
  treatment_id uuid NOT NULL REFERENCES public.treatments(id)
                          ON UPDATE CASCADE ON DELETE RESTRICT,
  role         text NOT NULL DEFAULT 'primary',  -- 'primary', 'control', 'vehicle', ...
  applied_at   timestamptz,
  stage        text,           -- e.g. '1-cell', 'blastula', '24hpf'
  notes        text,
  PRIMARY KEY (clutch_id, treatment_id, role)
);

-- 3. join_treatment_plasmids
CREATE TABLE IF NOT EXISTS public.join_treatment_plasmids (
  treatment_id uuid NOT NULL REFERENCES public.treatments(id)
                          ON UPDATE CASCADE ON DELETE CASCADE,
  plasmid_id   uuid NOT NULL REFERENCES public.plasmids(id)
                          ON UPDATE CASCADE ON DELETE RESTRICT,
  amount       numeric,
  amount_units text,
  notes        text,
  PRIMARY KEY (treatment_id, plasmid_id)
);

-- 4. join_treatment_rnas
CREATE TABLE IF NOT EXISTS public.join_treatment_rnas (
  treatment_id uuid NOT NULL REFERENCES public.treatments(id)
                          ON UPDATE CASCADE ON DELETE CASCADE,
  rna_id       uuid NOT NULL REFERENCES public.rnas(id)
                          ON UPDATE CASCADE ON DELETE RESTRICT,
  amount       numeric,
  amount_units text,
  notes        text,
  PRIMARY KEY (treatment_id, rna_id)
);

-- 5. join_treatment_crisprs
CREATE TABLE IF NOT EXISTS public.join_treatment_crisprs (
  treatment_id uuid NOT NULL REFERENCES public.treatments(id)
                          ON UPDATE CASCADE ON DELETE CASCADE,
  crispr_id    uuid NOT NULL,
  amount       numeric,
  amount_units text,
  notes        text,
  PRIMARY KEY (treatment_id, crispr_id)
);

-- 6. join_treatment_dyes
CREATE TABLE IF NOT EXISTS public.join_treatment_dyes (
  treatment_id uuid NOT NULL REFERENCES public.treatments(id)
                          ON UPDATE CASCADE ON DELETE CASCADE,
  dye_id       uuid NOT NULL REFERENCES public.dyes(id)
                          ON UPDATE CASCADE ON DELETE RESTRICT,
  concentration        numeric,
  concentration_units  text,
  notes        text,
  PRIMARY KEY (treatment_id, dye_id)
);

-- 7. Drop any old v_fusion_sources + treatment_fusions table
DROP VIEW IF EXISTS public.v_fusion_sources CASCADE;
DROP TABLE IF EXISTS public.treatment_fusions CASCADE;

-- 8. treatment_fusions as a view (derived via plasmids/RNAs)
CREATE VIEW public.treatment_fusions AS
  -- Plasmid-driven fusions
  SELECT DISTINCT
    tp.treatment_id,
    pf.fusion_id,
    'plasmid'        AS source,
    pl.code          AS source_detail
  FROM public.join_treatment_plasmids tp
  JOIN public.plasmids pl
    ON pl.id = tp.plasmid_id
  JOIN public.join_plasmid_fusions pf
    ON pf.plasmid_id = pl.id

  UNION ALL

  -- RNA-driven fusions (no assumption about rnas.code; leave detail NULL for now)
  SELECT DISTINCT
    tr.treatment_id,
    rf.fusion_id,
    'rna'            AS source,
    NULL::text       AS source_detail
  FROM public.join_treatment_rnas tr
  JOIN public.rnas r
    ON r.id = tr.rna_id
  JOIN public.join_rna_fusions rf
    ON rf.rna_id = r.id;

-- 9. v_fusion_sources: genotype_fusions ∪ treatment_fusions
CREATE VIEW public.v_fusion_sources AS
  SELECT
    'genotype'                 AS source_type,
    gf.genotype_code           AS genotype_code,
    NULL::uuid                 AS treatment_id,
    fu.id                      AS fusion_id,
    fl.id                      AS fluor_id,
    fl.fluor_code,
    tg.id                      AS tag_id,
    tg.tag_code,
    gf.source,
    gf.source_detail
  FROM public.genotype_fusions gf
  JOIN public.fusions fu  ON fu.id = gf.fusion_id
  JOIN public.fluors fl   ON fl.id = fu.fluor_id
  LEFT JOIN public.tags tg ON tg.id = fu.tag_id

  UNION ALL

  SELECT
    'treatment'                AS source_type,
    NULL::text                 AS genotype_code,
    tf.treatment_id,
    fu.id                      AS fusion_id,
    fl.id                      AS fluor_id,
    fl.fluor_code,
    tg.id                      AS tag_id,
    tg.tag_code,
    tf.source,
    tf.source_detail
  FROM public.treatment_fusions tf
  JOIN public.fusions fu  ON fu.id = tf.fusion_id
  JOIN public.fluors fl   ON fl.id = fu.fluor_id
  LEFT JOIN public.tags tg ON tg.id = fu.tag_id;

COMMIT;
