-- CARP v7 Core Schema
-- Baseline schema for a clean v7 database.
-- NOTE: This is designed for an EMPTY DB. If you run this on an existing DB,
-- you may need to drop/rename old tables first.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- 1. FISH GROUPS (GENOTYPE LINES)
-- ============================================================

CREATE TABLE IF NOT EXISTS public.fish_group (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  group_code    text UNIQUE NOT NULL,         -- e.g. "CASPER", "MGCO-35-F1"
  description   text,
  source_system text NOT NULL DEFAULT 'core', -- 'core' or 'legacy'
  notes         text,
  created_at    timestamptz NOT NULL DEFAULT now()
);

-- ============================================================
-- 2. FISH INSTANCES (INDIVIDUAL FISH)
-- ============================================================

CREATE TABLE IF NOT EXISTS public.fish_instance (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  fish_code            text UNIQUE NOT NULL,        -- FSH-xxxxx or legacy virtual code
  fish_group_id        uuid NULL
    REFERENCES public.fish_group(id)
    ON UPDATE CASCADE ON DELETE SET NULL,
  birthday             date,
  genetic_background   text,
  line_building_stage  text,                       -- P0/F0/F1/F2/etc
  nickname             text,
  notes                text,
  created_at           timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_fish_instance_group_id
  ON public.fish_instance (fish_group_id);

-- ============================================================
-- 3. GENETICS: TRANSGENES & ALLELES
-- ============================================================

CREATE TABLE IF NOT EXISTS public.transgenes (
  transgene_base_code text PRIMARY KEY,   -- e.g. "pDQM005"
  description         text,
  created_at          timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.transgene_alleles (
  transgene_base_code text NOT NULL,
  allele_number       integer NOT NULL,
  allele_name         text,
  allele_nickname     text,
  notes               text,
  created_at          timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT pk_transgene_alleles
    PRIMARY KEY (transgene_base_code, allele_number),

  CONSTRAINT fk_transgene_alleles_transgene
    FOREIGN KEY (transgene_base_code)
    REFERENCES public.transgenes(transgene_base_code)
    ON UPDATE CASCADE ON DELETE CASCADE
);

-- What alleles each fish_instance carries
CREATE TABLE IF NOT EXISTS public.join_fish_transgene_alleles (
  fish_id             uuid NOT NULL,
  transgene_base_code text NOT NULL,
  allele_number       integer NOT NULL,
  zygosity            text,                        -- "Het","Hom","Unknown" etc.
  created_at          timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT pk_join_fish_transgene_alleles
    PRIMARY KEY (fish_id, transgene_base_code, allele_number),

  CONSTRAINT fk_jfta_fish
    FOREIGN KEY (fish_id)
    REFERENCES public.fish_instance(id)
    ON UPDATE CASCADE ON DELETE CASCADE,

  CONSTRAINT fk_jfta_transgene_allele
    FOREIGN KEY (transgene_base_code, allele_number)
    REFERENCES public.transgene_alleles(transgene_base_code, allele_number)
    ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_jfta_fish_id
  ON public.join_fish_transgene_alleles (fish_id);

CREATE INDEX IF NOT EXISTS idx_jfta_transgene
  ON public.join_fish_transgene_alleles (transgene_base_code, allele_number);

-- ============================================================
-- 4. TREATMENTS (ATTACH TO FISH_INSTANCE)
-- ============================================================

CREATE TABLE IF NOT EXISTS public.treatments (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  treat_code  text UNIQUE NOT NULL,         -- canonical code, e.g. "inj_pDQM117_JF635"
  kind_code   text NOT NULL,                -- 'plasmid','rna','dye','chemical','crispr',...
  treat_text  text,                         -- human-friendly label
  notes       text,
  created_at  timestamptz NOT NULL DEFAULT now()
);

-- Treatments applied to fish_instance
CREATE TABLE IF NOT EXISTS public.join_fish_treatments (
  fish_id      uuid NOT NULL,
  treatment_id uuid NOT NULL,
  applied_at   timestamptz,
  dose         text,
  notes        text,
  created_at   timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT pk_join_fish_treatments
    PRIMARY KEY (fish_id, treatment_id),

  CONSTRAINT fk_jft_fish
    FOREIGN KEY (fish_id)
    REFERENCES public.fish_instance(id)
    ON UPDATE CASCADE ON DELETE CASCADE,

  CONSTRAINT fk_jft_treatment
    FOREIGN KEY (treatment_id)
    REFERENCES public.treatments(id)
    ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_jft_fish_id
  ON public.join_fish_treatments (fish_id);

CREATE INDEX IF NOT EXISTS idx_jft_treatment_id
  ON public.join_fish_treatments (treatment_id);

-- Optional: mapping dye-only treatments (if needed)
CREATE TABLE IF NOT EXISTS public.join_treatment_dyes (
  treatment_id uuid NOT NULL,
  dye_id       uuid NOT NULL,
  notes        text,
  created_at   timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT pk_join_treatment_dyes
    PRIMARY KEY (treatment_id, dye_id)
);

-- ============================================================
-- 5. IMAGING: PLATES → SLOTS → ROIS → FILES
-- ============================================================

-- Imaging plates (per imaging run / physical plate)
CREATE TABLE IF NOT EXISTS public.plates (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  plate_code  text UNIQUE NOT NULL,       -- e.g. "aang_2025-04-28_mem_histone"
  description text,
  created_at  timestamptz NOT NULL DEFAULT now()
);

-- Imaging slots: each slot holds exactly one fish_instance
CREATE TABLE IF NOT EXISTS public.imaging_slots (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  plate_id             uuid NOT NULL,
  slot_label           text NOT NULL,     -- "fish1_72hpf","A01", etc.
  fish_id              uuid NOT NULL,     -- FK to fish_instance
  experiment_nickname  text,              -- "mem_histone","lifeact-mSG", etc.
  notes                text,
  created_at           timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT uq_imaging_slots_plate_slot UNIQUE (plate_id, slot_label),

  CONSTRAINT fk_imaging_slots_plate
    FOREIGN KEY (plate_id)
    REFERENCES public.plates(id)
    ON UPDATE CASCADE ON DELETE CASCADE,

  CONSTRAINT fk_imaging_slots_fish
    FOREIGN KEY (fish_id)
    REFERENCES public.fish_instance(id)
    ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_imaging_slots_plate_id
  ON public.imaging_slots (plate_id);

CREATE INDEX IF NOT EXISTS idx_imaging_slots_fish_id
  ON public.imaging_slots (fish_id);

-- Imaging ROIs (regions of interest under each slot)
CREATE TABLE IF NOT EXISTS public.imaging_rois (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slot_id       uuid NOT NULL,
  roi_index     integer NOT NULL,
  roi_name      text,
  data_path     text,                 -- directory / path for this ROI
  channel_info  jsonb,                -- optional structured info
  notes         text,
  created_at    timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT uq_imaging_rois_slot_index UNIQUE (slot_id, roi_index),

  CONSTRAINT fk_imaging_rois_slot
    FOREIGN KEY (slot_id)
    REFERENCES public.imaging_slots(id)
    ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_imaging_rois_slot_id
  ON public.imaging_rois (slot_id);

-- Imaging ROI files (actual TIFF/Zarr paths)
CREATE TABLE IF NOT EXISTS public.imaging_roi_files (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  roi_id     uuid NOT NULL,
  path       text NOT NULL,
  kind       text,                     -- 'tif','zarr','ome-tiff', etc.
  channel    text,
  notes      text,
  created_at timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT fk_imaging_roi_files_roi
    FOREIGN KEY (roi_id)
    REFERENCES public.imaging_rois(id)
    ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_imaging_roi_files_roi_id
  ON public.imaging_roi_files (roi_id);

-- ============================================================
-- END: CARP v7 core schema baseline
-- ============================================================
