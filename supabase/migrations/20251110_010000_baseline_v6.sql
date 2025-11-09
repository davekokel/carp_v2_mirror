BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.fluors (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  fluor_code text UNIQUE NOT NULL,
  fluor_name text,
  excitation_nm integer,
  emission_nm integer,
  alt_names text,
  notes text,
  created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.tags (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tag_code text UNIQUE NOT NULL,
  tag_name text,
  localization text,
  citation_link text,
  note text,
  created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.dyes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  dye_code text UNIQUE NOT NULL,
  dye_name text,
  excitation_nm integer,
  emission_nm integer,
  alt_names text,
  notes text,
  localization text,
  created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.plasmids (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code text UNIQUE NOT NULL,
  name text,
  created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.rnas (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  rna_code text UNIQUE NOT NULL,
  created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.crispr_knockins (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  knockin_code text UNIQUE NOT NULL,
  description text,
  created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.fusions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  fluor_id uuid NULL,
  tag_id uuid NOT NULL,
  created_at timestamptz DEFAULT now(),
  CONSTRAINT fk_fusions_fluor_id__fluors_id FOREIGN KEY (fluor_id) REFERENCES public.fluors(id) DEFERRABLE INITIALLY DEFERRED,
  CONSTRAINT fk_fusions_tag_id__tags_id FOREIGN KEY (tag_id) REFERENCES public.tags(id) DEFERRABLE INITIALLY DEFERRED,
  CONSTRAINT uq_fusions_fluor_tag UNIQUE (fluor_id, tag_id)
);
CREATE INDEX IF NOT EXISTS idx_fusions_fluor_id ON public.fusions(fluor_id);
CREATE INDEX IF NOT EXISTS idx_fusions_tag_id ON public.fusions(tag_id);

CREATE TABLE IF NOT EXISTS public.join_plasmid_fusions (
  plasmid_id uuid NOT NULL,
  fusion_id uuid NOT NULL,
  created_at timestamptz DEFAULT now(),
  PRIMARY KEY (plasmid_id, fusion_id),
  CONSTRAINT fk_jpf_plasmid_id__plasmids_id FOREIGN KEY (plasmid_id) REFERENCES public.plasmids(id) DEFERRABLE INITIALLY DEFERRED,
  CONSTRAINT fk_jpf_fusion_id__fusions_id FOREIGN KEY (fusion_id) REFERENCES public.fusions(id) DEFERRABLE INITIALLY DEFERRED
);
CREATE INDEX IF NOT EXISTS idx_jpf_plasmid_id ON public.join_plasmid_fusions(plasmid_id);
CREATE INDEX IF NOT EXISTS idx_jpf_fusion_id ON public.join_plasmid_fusions(fusion_id);

CREATE TABLE IF NOT EXISTS public.join_rna_fusions (
  rna_id uuid NOT NULL,
  fusion_id uuid NOT NULL,
  created_at timestamptz DEFAULT now(),
  PRIMARY KEY (rna_id, fusion_id),
  CONSTRAINT fk_jrf_rna_id__rnas_id FOREIGN KEY (rna_id) REFERENCES public.rnas(id) DEFERRABLE INITIALLY DEFERRED,
  CONSTRAINT fk_jrf_fusion_id__fusions_id FOREIGN KEY (fusion_id) REFERENCES public.fusions(id) DEFERRABLE INITIALLY DEFERRED
);
CREATE INDEX IF NOT EXISTS idx_jrf_rna_id ON public.join_rna_fusions(rna_id);
CREATE INDEX IF NOT EXISTS idx_jrf_fusion_id ON public.join_rna_fusions(fusion_id);

CREATE TABLE IF NOT EXISTS public.join_crispr_fusions (
  knockin_id uuid NOT NULL,
  fusion_id uuid NOT NULL,
  created_at timestamptz DEFAULT now(),
  PRIMARY KEY (knockin_id, fusion_id),
  CONSTRAINT fk_jcf_knockin_id__crispr_knockins_id FOREIGN KEY (knockin_id) REFERENCES public.crispr_knockins(id) DEFERRABLE INITIALLY DEFERRED,
  CONSTRAINT fk_jcf_fusion_id__fusions_id FOREIGN KEY (fusion_id) REFERENCES public.fusions(id) DEFERRABLE INITIALLY DEFERRED
);
CREATE INDEX IF NOT EXISTS idx_jcf_knockin_id ON public.join_crispr_fusions(knockin_id);
CREATE INDEX IF NOT EXISTS idx_jcf_fusion_id ON public.join_crispr_fusions(fusion_id);

CREATE TABLE IF NOT EXISTS public.treatments_fluorescent (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ft_code text UNIQUE NOT NULL,
  ft_text text,
  created_by text,
  created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.join_ft_dyes (
  ft_id uuid NOT NULL,
  dye_id uuid NOT NULL,
  created_at timestamptz DEFAULT now(),
  PRIMARY KEY (ft_id, dye_id),
  CONSTRAINT fk_join_ft_dyes_ft_id__treatments_fluorescent_id FOREIGN KEY (ft_id) REFERENCES public.treatments_fluorescent(id) DEFERRABLE INITIALLY DEFERRED,
  CONSTRAINT fk_join_ft_dyes_dye_id__dyes_id FOREIGN KEY (dye_id) REFERENCES public.dyes(id) DEFERRABLE INITIALLY DEFERRED
);
CREATE INDEX IF NOT EXISTS idx_join_ft_dyes_ft_id ON public.join_ft_dyes(ft_id);
CREATE INDEX IF NOT EXISTS idx_join_ft_dyes_dye_id ON public.join_ft_dyes(dye_id);

CREATE TABLE IF NOT EXISTS public.join_ft_fusions (
  ft_id uuid NOT NULL,
  fusion_id uuid NOT NULL,
  created_at timestamptz DEFAULT now(),
  PRIMARY KEY (ft_id, fusion_id),
  CONSTRAINT fk_join_ft_fusions_ft_id__treatments_fluorescent_id FOREIGN KEY (ft_id) REFERENCES public.treatments_fluorescent(id) DEFERRABLE INITIALLY DEFERRED,
  CONSTRAINT fk_join_ft_fusions_fusion_id__fusions_id FOREIGN KEY (fusion_id) REFERENCES public.fusions(id) DEFERRABLE INITIALLY DEFERRED
);
CREATE INDEX IF NOT EXISTS idx_join_ft_fusions_ft_id ON public.join_ft_fusions(ft_id);
CREATE INDEX IF NOT EXISTS idx_join_ft_fusions_fus_id ON public.join_ft_fusions(fusion_id);

CREATE TABLE IF NOT EXISTS public.fish (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  fish_code text UNIQUE NOT NULL,
  nickname text,
  genetic_background text,
  in_breeding_stage text,
  identity_key text,
  identity_hash text,
  birthday date,
  created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.transgenes (
  transgene_base_code text PRIMARY KEY,
  name text,
  created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.transgene_alleles (
  transgene_base_code text NOT NULL,
  allele_number integer NOT NULL,
  allele_nickname text,
  allele_name text,
  created_at timestamptz DEFAULT now(),
  PRIMARY KEY (transgene_base_code, allele_number),
  CONSTRAINT fk_ta_transgene__transgenes FOREIGN KEY (transgene_base_code) REFERENCES public.transgenes(transgene_base_code) DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE IF NOT EXISTS public.join_fish_transgene_alleles (
  fish_id uuid NOT NULL,
  transgene_base_code text NOT NULL,
  allele_number integer NOT NULL,
  zygosity text,
  created_at timestamptz DEFAULT now(),
  PRIMARY KEY (fish_id, transgene_base_code, allele_number),
  CONSTRAINT fk_jfta_fish_id__fish_id FOREIGN KEY (fish_id) REFERENCES public.fish(id) DEFERRABLE INITIALLY DEFERRED,
  CONSTRAINT fk_jftga_base_allele__transgene_alleles FOREIGN KEY (transgene_base_code, allele_number) REFERENCES public.transgene_alleles(transgene_base_code, allele_number) DEFERRABLE INITIALLY DEFERRED
);
CREATE INDEX IF NOT EXISTS idx_jfta_fish_id ON public.join_fish_transgene_alleles(fish_id);

CREATE TABLE IF NOT EXISTS public.locations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code text UNIQUE,
  name text,
  created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.tanks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tank_code text UNIQUE NOT NULL,
  location_id uuid,
  status text,
  created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.tank_pairs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tank_pair_code text UNIQUE NOT NULL,
  mother_tank_id uuid,
  father_tank_id uuid,
  created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.crosses (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  cross_run_code text UNIQUE,
  tank_pair_id uuid NOT NULL,
  created_at timestamptz DEFAULT now(),
  CONSTRAINT fk_crosses_tank_pair_id__tank_pairs_id FOREIGN KEY (tank_pair_id) REFERENCES public.tank_pairs(id) DEFERRABLE INITIALLY DEFERRED
);
CREATE INDEX IF NOT EXISTS idx_crosses_tank_pair_id ON public.crosses(tank_pair_id);

CREATE TABLE IF NOT EXISTS public.clutch_instances (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  clutch_instance_code text UNIQUE,
  cross_instance_id uuid NOT NULL,
  created_at timestamptz DEFAULT now(),
  CONSTRAINT fk_clutch_instances_cross_instance_id__crosses_id FOREIGN KEY (cross_instance_id) REFERENCES public.crosses(id) DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE IF NOT EXISTS public.treated_clutches (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  treated_clutch_code text UNIQUE,
  clutch_instance_id uuid NOT NULL,
  created_by text,
  created_at timestamptz DEFAULT now(),
  CONSTRAINT fk_treated_clutches_clutch_instance_id__clutch_instances_id FOREIGN KEY (clutch_instance_id) REFERENCES public.clutch_instances(id) DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE IF NOT EXISTS public.treatments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  treat_code text UNIQUE NOT NULL,
  kind text,
  treat_text text,
  created_by text,
  created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.join_clutch_treatments (
  treated_clutch_id uuid NOT NULL,
  treatment_id uuid NOT NULL,
  created_at timestamptz DEFAULT now(),
  PRIMARY KEY (treated_clutch_id, treatment_id),
  CONSTRAINT fk_jct_treated_clutch_id__treated_clutches_id FOREIGN KEY (treated_clutch_id) REFERENCES public.treated_clutches(id) DEFERRABLE INITIALLY DEFERRED,
  CONSTRAINT fk_jct_treatment_id__treatments_id FOREIGN KEY (treatment_id) REFERENCES public.treatments(id) DEFERRABLE INITIALLY DEFERRED
);
CREATE INDEX IF NOT EXISTS idx_jct_treated_clutch_id ON public.join_clutch_treatments(treated_clutch_id);
CREATE INDEX IF NOT EXISTS idx_jct_treatment_id ON public.join_clutch_treatments(treatment_id);

CREATE TABLE IF NOT EXISTS public.plates (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  plate_code text UNIQUE NOT NULL,
  format_code text,
  created_by text,
  created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.plate_slots (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  plate_id uuid NOT NULL,
  row_idx integer NOT NULL,
  col_idx integer NOT NULL,
  treated_clutch_id uuid,
  fish_id uuid,
  orientation text,
  created_at timestamptz DEFAULT now(),
  CONSTRAINT uq_plate_slots_unique_location UNIQUE (plate_id, row_idx, col_idx),
  CONSTRAINT fk_plate_slots_plate_id__plates_id FOREIGN KEY (plate_id) REFERENCES public.plates(id) DEFERRABLE INITIALLY DEFERRED,
  CONSTRAINT fk_plate_slots_treated_clutch_id__treated_clutches_id FOREIGN KEY (treated_clutch_id) REFERENCES public.treated_clutches(id) DEFERRABLE INITIALLY DEFERRED,
  CONSTRAINT fk_plate_slots_fish_id__fish_id FOREIGN KEY (fish_id) REFERENCES public.fish(id) DEFERRABLE INITIALLY DEFERRED
);
CREATE INDEX IF NOT EXISTS idx_plate_slots_plate_id ON public.plate_slots(plate_id);

CREATE TABLE IF NOT EXISTS public.join_fish_treatments_fluorescent (
  fish_id uuid NOT NULL,
  ft_id uuid NOT NULL,
  allele_number integer,
  zygosity text,
  created_at timestamptz DEFAULT now(),
  PRIMARY KEY (fish_id, ft_id),
  CONSTRAINT fk_jfft_fish_id__fish_id FOREIGN KEY (fish_id) REFERENCES public.fish(id) DEFERRABLE INITIALLY DEFERRED,
  CONSTRAINT fk_jfft_ft_id__treatments_fluorescent_id FOREIGN KEY (ft_id) REFERENCES public.treatments_fluorescent(id) DEFERRABLE INITIALLY DEFERRED
);

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname='annotation_target_kind') THEN
    CREATE TYPE annotation_target_kind AS ENUM ('fish','clutch_inst','cross','tank','plasmid');
  END IF;
END$$;

CREATE TABLE IF NOT EXISTS public.join_annotations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  target_kind annotation_target_kind,
  target_id uuid,
  kind_code text,
  value_text text,
  value_num double precision,
  created_at timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_join_annotations_kind_id ON public.join_annotations(target_kind, target_id);

CREATE OR REPLACE FUNCTION public.enforce_join_annotations_fk()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE ok boolean;
BEGIN
  IF NEW.target_id IS NULL OR NEW.target_kind IS NULL THEN
    RAISE EXCEPTION 'join_annotations requires target_kind and target_id';
  END IF;
  CASE NEW.target_kind
    WHEN 'fish'        THEN SELECT EXISTS (SELECT 1 FROM public.fish             p WHERE p.id=NEW.target_id) INTO ok;
    WHEN 'clutch_inst' THEN SELECT EXISTS (SELECT 1 FROM public.clutch_instances p WHERE p.id=NEW.target_id) INTO ok;
    WHEN 'cross'       THEN SELECT EXISTS (SELECT 1 FROM public.crosses          p WHERE p.id=NEW.target_id) INTO ok;
    WHEN 'tank'        THEN SELECT EXISTS (SELECT 1 FROM public.tanks            p WHERE p.id=NEW.target_id) INTO ok;
    WHEN 'plasmid'     THEN SELECT EXISTS (SELECT 1 FROM public.plasmids         p WHERE p.id=NEW.target_id) INTO ok;
    ELSE RAISE EXCEPTION 'Unknown target_kind: %', NEW.target_kind;
  END CASE;
  IF NOT ok THEN
    RAISE EXCEPTION 'join_annotations % → % does not reference an existing row', NEW.target_kind, NEW.target_id;
  END IF;
  RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS trg_enforce_join_annotations_fk ON public.join_annotations;
CREATE CONSTRAINT TRIGGER trg_enforce_join_annotations_fk
AFTER INSERT OR UPDATE ON public.join_annotations
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION public.enforce_join_annotations_fk();

DROP VIEW IF EXISTS public.v_fish_main;
CREATE VIEW public.v_fish_main AS
WITH alleles AS (
  SELECT f.fish_code, jfta.transgene_base_code, jfta.allele_number, ta.allele_name, ta.allele_nickname
  FROM public.fish f
  JOIN public.join_fish_transgene_alleles jfta ON jfta.fish_id = f.id
  JOIN public.transgene_alleles ta ON ta.transgene_base_code=jfta.transgene_base_code AND ta.allele_number=jfta.allele_number
),
pick AS (
  SELECT DISTINCT ON (a.fish_code) a.fish_code, a.transgene_base_code, a.allele_number, a.allele_name, a.allele_nickname
  FROM alleles a
  ORDER BY a.fish_code, a.allele_number DESC
)
SELECT
  f.id AS fish_id,
  f.fish_code,
  f.created_at,
  COALESCE(pick.transgene_base_code,'') AS transgene_base_code,
  COALESCE(pick.allele_nickname,'') AS allele_nickname,
  COALESCE(pick.allele_number,0) AS allele_number,
  COALESCE(pick.allele_name,'') AS allele_name,
  'Tg('||COALESCE(pick.transgene_base_code,'')||')'||COALESCE(pick.allele_nickname,'') AS transgene_pretty_nickname,
  'Tg('||COALESCE(pick.transgene_base_code,'')||')'||COALESCE(pick.allele_name,'') AS transgene_pretty_name
FROM public.fish f
LEFT JOIN pick ON pick.fish_code = f.fish_code;

DROP VIEW IF EXISTS public.v_plasmids;
CREATE VIEW public.v_plasmids AS
SELECT
  p.id AS plasmid_id,
  p.code AS plasmid_code,
  p.name AS plasmid_name,
  p.created_at,
  COALESCE(string_agg(DISTINCT fl.fluor_code, ', ' ORDER BY fl.fluor_code) FILTER (WHERE fl.id IS NOT NULL),'') AS fluors,
  COALESCE(string_agg(DISTINCT tg.tag_code, ', ' ORDER BY tg.tag_code) FILTER (WHERE tg.id IS NOT NULL),'') AS tags
FROM public.plasmids p
LEFT JOIN public.join_plasmid_fusions jpf ON jpf.plasmid_id = p.id
LEFT JOIN public.fusions fu ON fu.id = jpf.fusion_id
LEFT JOIN public.fluors fl ON fl.id = fu.fluor_id
LEFT JOIN public.tags tg ON tg.id = fu.tag_id
GROUP BY p.id, p.code, p.name, p.created_at;

DROP VIEW IF EXISTS public.v_rnas;
CREATE VIEW public.v_rnas AS
SELECT
  r.id AS rna_id,
  r.rna_code,
  r.created_at,
  COALESCE(string_agg(DISTINCT fl.fluor_code, ', ' ORDER BY fl.fluor_code) FILTER (WHERE fl.id IS NOT NULL),'') AS fluors,
  COALESCE(string_agg(DISTINCT tg.tag_code, ', ' ORDER BY tg.tag_code) FILTER (WHERE tg.id IS NOT NULL),'') AS tags
FROM public.rnas r
LEFT JOIN public.join_rna_fusions jrf ON jrf.rna_id = r.id
LEFT JOIN public.fusions fu ON fu.id = jrf.fusion_id
LEFT JOIN public.fluors fl ON fl.id = fu.fluor_id
LEFT JOIN public.tags tg ON tg.id = fu.tag_id
GROUP BY r.id, r.rna_code, r.created_at;

COMMIT;
