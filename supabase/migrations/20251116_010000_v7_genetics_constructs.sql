CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Fluorophores
CREATE TABLE IF NOT EXISTS public.fluors (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  fluor_code    text UNIQUE NOT NULL,
  fluor_name    text,
  excitation_nm integer,
  emission_nm   integer,
  alt_names     text[],
  notes         text,
  created_at    timestamptz NOT NULL DEFAULT now()
);

-- Tags
CREATE TABLE IF NOT EXISTS public.tags (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tag_code      text UNIQUE NOT NULL,
  tag_name      text,
  alt_names     text[],
  localization  text,
  notes         text,
  created_at    timestamptz NOT NULL DEFAULT now()
);

-- Fusions
CREATE TABLE IF NOT EXISTS public.fusions (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  fluor_id   uuid NOT NULL,
  tag_id     uuid NULL,
  tag_pos    text,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT fk_fusions_fluor
    FOREIGN KEY (fluor_id) REFERENCES public.fluors(id)
    ON UPDATE CASCADE ON DELETE SET NULL,
  CONSTRAINT fk_fusions_tag
    FOREIGN KEY (tag_id)   REFERENCES public.tags(id)
    ON UPDATE CASCADE ON DELETE SET NULL,
  CONSTRAINT ck_fusions_tag_pos
    CHECK (tag_pos IS NULL OR tag_pos IN ('N','C'))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_fusions_fluor_when_tag_null
  ON public.fusions (fluor_id)
  WHERE tag_id IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_fusions_fluor_tag_pos_notnull
  ON public.fusions (fluor_id, tag_id, tag_pos)
  WHERE tag_id IS NOT NULL;

-- Plasmids
CREATE TABLE IF NOT EXISTS public.plasmids (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code              text UNIQUE NOT NULL,
  plasmid_base_code text,
  name              text,
  nickname          text,
  notes             text,
  created_at        timestamptz NOT NULL DEFAULT now()
);

-- RNAs
CREATE TABLE IF NOT EXISTS public.rnas (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  rna_base_code text UNIQUE NOT NULL,
  name          text,
  notes         text,
  created_at    timestamptz NOT NULL DEFAULT now()
);

-- Dyes
CREATE TABLE IF NOT EXISTS public.dyes (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  dye_base_code text UNIQUE NOT NULL,
  name          text,
  notes         text,
  created_at    timestamptz NOT NULL DEFAULT now()
);

-- Plasmid ↔ fusion
CREATE TABLE IF NOT EXISTS public.join_plasmid_fusions (
  plasmid_id uuid NOT NULL,
  fusion_id  uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT pk_join_plasmid_fusions PRIMARY KEY (plasmid_id, fusion_id),
  CONSTRAINT fk_jpf_plasmid
    FOREIGN KEY (plasmid_id) REFERENCES public.plasmids(id)
    ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT fk_jpf_fusion
    FOREIGN KEY (fusion_id)  REFERENCES public.fusions(id)
    ON UPDATE CASCADE ON DELETE CASCADE
);

-- RNA ↔ fusion
CREATE TABLE IF NOT EXISTS public.join_rna_fusions (
  rna_id     uuid NOT NULL,
  fusion_id  uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT pk_join_rna_fusions PRIMARY KEY (rna_id, fusion_id),
  CONSTRAINT fk_jrf_rna
    FOREIGN KEY (rna_id)    REFERENCES public.rnas(id)
    ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT fk_jrf_fusion
    FOREIGN KEY (fusion_id) REFERENCES public.fusions(id)
    ON UPDATE CASCADE ON DELETE CASCADE
);

-- Canonical fusion labels
CREATE OR REPLACE VIEW public.v_fusion_labels AS
SELECT
  f.id AS fusion_id,
  fl.fluor_code,
  tg.tag_code,
  f.tag_pos,
  CASE
    WHEN f.tag_id IS NULL THEN fl.fluor_code
    WHEN f.tag_pos IS NULL THEN fl.fluor_code || '::' || tg.tag_code
    ELSE fl.fluor_code || '::' || tg.tag_code || '(' || f.tag_pos || ')'
  END AS fusion_label
FROM public.fusions f
JOIN public.fluors fl ON fl.id = f.fluor_id
LEFT JOIN public.tags tg ON tg.id = f.tag_id;
