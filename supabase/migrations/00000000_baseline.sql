BEGIN;

CREATE SCHEMA IF NOT EXISTS public;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS public.fluors(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  fluor_code text UNIQUE NOT NULL,
  fluor_name text,
  excitation_nm integer,
  emission_nm integer,
  alt_names text[],
  notes text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.tags(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tag_code text UNIQUE NOT NULL,
  tag_name text,
  alt_names text[],
  notes text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.dyes(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  dye_code text UNIQUE NOT NULL,
  dye_name text,
  excitation_nm integer,
  emission_nm integer,
  alt_names text[],
  notes text,
  localization text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.fusions(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  fluor_id uuid NOT NULL REFERENCES public.fluors(id),
  tag_id uuid NULL REFERENCES public.tags(id),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_fusions_fluor_tag_notnull ON public.fusions(fluor_id,tag_id) WHERE tag_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_fusions_fluor_when_tag_null ON public.fusions(fluor_id) WHERE tag_id IS NULL;

CREATE TABLE IF NOT EXISTS public.rnas(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  rna_code text UNIQUE NOT NULL,
  nickname text,
  notes text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.join_rna_fusions(
  rna_id uuid NOT NULL REFERENCES public.rnas(id) ON DELETE CASCADE,
  fusion_id uuid NOT NULL REFERENCES public.fusions(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (rna_id,fusion_id)
);

CREATE TABLE IF NOT EXISTS public.plasmids(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code text UNIQUE NOT NULL,
  name text,
  nickname text,
  resistance text,
  notes text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.join_plasmid_fusions(
  plasmid_id uuid NOT NULL REFERENCES public.plasmids(id) ON DELETE CASCADE,
  fusion_id uuid NOT NULL REFERENCES public.fusions(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY(plasmid_id,fusion_id)
);

CREATE TABLE IF NOT EXISTS public.crispr_knockins(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  knockin_code text UNIQUE NOT NULL,
  description text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.join_crispr_fusions(
  knockin_id uuid NOT NULL REFERENCES public.crispr_knockins(id) ON DELETE CASCADE,
  fusion_id uuid NOT NULL REFERENCES public.fusions(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY(knockin_id,fusion_id)
);

CREATE TABLE IF NOT EXISTS public.fish(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  fish_code text UNIQUE NOT NULL,
  nickname text,
  genetic_background text,
  in_breeding_stage text,
  identity_key text,
  identity_hash text,
  birthday date,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.transgenes(
  transgene_base_code text PRIMARY KEY,
  name text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.transgene_alleles(
  transgene_base_code text NOT NULL REFERENCES public.transgenes(transgene_base_code) ON DELETE CASCADE,
  allele_number integer NOT NULL,
  allele_nickname text,
  allele_name text,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY(transgene_base_code,allele_number)
);

CREATE TABLE IF NOT EXISTS public.join_fish_transgene_alleles(
  fish_id uuid NOT NULL REFERENCES public.fish(id) ON DELETE CASCADE,
  transgene_base_code text NOT NULL,
  allele_number integer NOT NULL,
  zygosity text,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY(fish_id,transgene_base_code,allele_number),
  FOREIGN KEY (transgene_base_code,allele_number)
    REFERENCES public.transgene_alleles(transgene_base_code,allele_number) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS public.locations(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code text UNIQUE NOT NULL,
  name text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.tanks(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tank_code text UNIQUE NOT NULL,
  location_id uuid REFERENCES public.locations(id),
  status text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.tank_pairs(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tank_pair_code text UNIQUE NOT NULL,
  mother_tank_id uuid REFERENCES public.tanks(id),
  father_tank_id uuid REFERENCES public.tanks(id),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.crosses(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  cross_run_code text UNIQUE,
  tank_pair_id uuid REFERENCES public.tank_pairs(id),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.clutch_instances(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  clutch_instance_code text UNIQUE,
  cross_instance_id uuid REFERENCES public.crosses(id),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.treated_clutches(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  treated_clutch_code text UNIQUE,
  clutch_instance_id uuid REFERENCES public.clutch_instances(id),
  fish_id uuid REFERENCES public.fish(id),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.plates(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  plate_code text UNIQUE NOT NULL,
  format_code text,
  created_by text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.plate_slots(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  plate_id uuid NOT NULL REFERENCES public.plates(id) ON DELETE CASCADE,
  row_idx integer,
  col_idx integer,
  treated_clutch_id uuid REFERENCES public.treated_clutches(id),
  orientation text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.treatments(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  treat_code text UNIQUE NOT NULL,
  kind_code text NOT NULL,
  treat_text text,
  created_by text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.join_clutch_treatments(
  treated_clutch_id uuid NOT NULL REFERENCES public.treated_clutches(id) ON DELETE CASCADE,
  treatment_id uuid NOT NULL REFERENCES public.treatments(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY(treated_clutch_id,treatment_id)
);

CREATE TABLE IF NOT EXISTS public.treatments_fluorescent(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ft_code text UNIQUE NOT NULL,
  ft_text text,
  created_by text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.join_ft_fusions(
  ft_id uuid NOT NULL REFERENCES public.treatments_fluorescent(id) ON DELETE CASCADE,
  fusion_id uuid NOT NULL REFERENCES public.fusions(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY(ft_id,fusion_id)
);

CREATE TABLE IF NOT EXISTS public.join_ft_dyes(
  ft_id uuid NOT NULL REFERENCES public.treatments_fluorescent(id) ON DELETE CASCADE,
  dye_id uuid NOT NULL REFERENCES public.dyes(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY(ft_id,dye_id)
);

CREATE TABLE IF NOT EXISTS public.join_fish_treatments_fluorescent(
  fish_id uuid NOT NULL REFERENCES public.fish(id) ON DELETE CASCADE,
  ft_id uuid NOT NULL REFERENCES public.treatments_fluorescent(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY(fish_id,ft_id)
);

CREATE TABLE IF NOT EXISTS public.join_annotations(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  target_kind text NOT NULL,
  target_id uuid NOT NULL,
  kind_code text NOT NULL,
  value_num numeric,
  value_text text,
  created_at timestamptz NOT NULL DEFAULT now()
);

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname='alias_target_kind') THEN
    CREATE TYPE public.alias_target_kind AS ENUM ('fluor','tag','dye','rna','plasmid','fish','tank','cross','clutch_inst','treated_clutch');
  END IF;
END$$;

CREATE TABLE IF NOT EXISTS public.join_aliases(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  target_kind public.alias_target_kind NOT NULL,
  target_id uuid NOT NULL,
  alias text NOT NULL,
  alias_norm text GENERATED ALWAYS AS (lower(btrim(alias))) STORED,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(target_kind,target_id,alias_norm)
);

CREATE OR REPLACE FUNCTION public.enforce_join_aliases_fk() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE ok boolean := false;
BEGIN
  IF NEW.target_kind='fluor' THEN SELECT TRUE INTO ok FROM public.fluors WHERE id=NEW.target_id;
  ELSIF NEW.target_kind='tag' THEN SELECT TRUE INTO ok FROM public.tags WHERE id=NEW.target_id;
  ELSIF NEW.target_kind='dye' THEN SELECT TRUE INTO ok FROM public.dyes WHERE id=NEW.target_id;
  ELSIF NEW.target_kind='rna' THEN SELECT TRUE INTO ok FROM public.rnas WHERE id=NEW.target_id;
  ELSIF NEW.target_kind='plasmid' THEN SELECT TRUE INTO ok FROM public.plasmids WHERE id=NEW.target_id;
  ELSIF NEW.target_kind='fish' THEN SELECT TRUE INTO ok FROM public.fish WHERE id=NEW.target_id;
  ELSIF NEW.target_kind='tank' THEN SELECT TRUE INTO ok FROM public.tanks WHERE id=NEW.target_id;
  ELSIF NEW.target_kind='cross' THEN SELECT TRUE INTO ok FROM public.crosses WHERE id=NEW.target_id;
  ELSIF NEW.target_kind='clutch_inst' THEN SELECT TRUE INTO ok FROM public.clutch_instances WHERE id=NEW.target_id;
  ELSIF NEW.target_kind='treated_clutch' THEN SELECT TRUE INTO ok FROM public.treated_clutches WHERE id=NEW.target_id;
  ELSE ok := TRUE;
  END IF;
  IF NOT ok THEN RAISE EXCEPTION 'join_aliases target_id % not found for kind %', NEW.target_id, NEW.target_kind; END IF;
  RETURN NEW;
END$$;

DROP TRIGGER IF EXISTS trg_enforce_join_aliases_fk ON public.join_aliases;
CREATE TRIGGER trg_enforce_join_aliases_fk
BEFORE INSERT OR UPDATE ON public.join_aliases
FOR EACH ROW EXECUTE FUNCTION public.enforce_join_aliases_fk();

CREATE OR REPLACE FUNCTION public.resolve_fluor_id(sym text) RETURNS uuid LANGUAGE sql STABLE AS $$
  WITH s AS (SELECT lower(btrim(sym)) k)
  SELECT id FROM public.fluors f JOIN s ON lower(f.fluor_code)=s.k OR lower(COALESCE(f.fluor_name,''))=s.k
  UNION
  SELECT target_id FROM public.join_aliases ja JOIN s ON ja.alias_norm=s.k WHERE ja.target_kind='fluor'::public.alias_target_kind
  LIMIT 1
$$;

CREATE OR REPLACE FUNCTION public.resolve_tag_id(sym text) RETURNS uuid LANGUAGE sql STABLE AS $$
  WITH s AS (SELECT lower(btrim(sym)) k)
  SELECT id FROM public.tags t JOIN s ON lower(t.tag_code)=s.k OR lower(COALESCE(t.tag_name,''))=s.k
  UNION
  SELECT target_id FROM public.join_aliases ja JOIN s ON ja.alias_norm=s.k WHERE ja.target_kind='tag'::public.alias_target_kind
  LIMIT 1
$$;

CREATE OR REPLACE FUNCTION public.resolve_dye_id(sym text) RETURNS uuid LANGUAGE sql STABLE AS $$
  WITH s AS (SELECT lower(btrim(sym)) k)
  SELECT id FROM public.dyes d JOIN s ON lower(d.dye_code)=s.k OR lower(COALESCE(d.dye_name,''))=s.k
  UNION
  SELECT target_id FROM public.join_aliases ja JOIN s ON ja.alias_norm=s.k WHERE ja.target_kind='dye'::public.alias_target_kind
  LIMIT 1
$$;

CREATE OR REPLACE FUNCTION public.resolve_fusion_id(combo text)
RETURNS uuid
LANGUAGE plpgsql
AS $$
DECLARE
  raw     text := btrim(COALESCE(combo,''));
  no_ws   text;
  parts   text[];
  leftp   text;
  rightp  text;
  fid     uuid;
  tid     uuid;
  existing uuid;
BEGIN
  IF raw='' THEN
    RETURN NULL;
  END IF;

  no_ws := regexp_replace(raw, '\s+', '', 'g');
  parts := regexp_split_to_array(no_ws, '::|[:/@+]');

  IF array_length(parts,1) IS NULL THEN
    RETURN NULL;
  ELSIF array_length(parts,1) = 1 THEN
    fid := public.resolve_fluor_id(parts[1]);
    tid := NULL;
  ELSE
    leftp  := parts[1];
    rightp := parts[array_length(parts,1)];

    fid := public.resolve_fluor_id(leftp);
    IF fid IS NOT NULL THEN
      tid := public.resolve_tag_id(rightp);
    ELSE
      fid := public.resolve_fluor_id(rightp);
      tid := public.resolve_tag_id(leftp);
    END IF;
  END IF;

  IF fid IS NULL THEN
    RETURN NULL;
  END IF;

  SELECT id INTO existing
  FROM public.fusions
  WHERE fluor_id=fid
    AND ((tid IS NULL AND tag_id IS NULL) OR tag_id=tid)
  LIMIT 1;

  IF existing IS NOT NULL THEN
    RETURN existing;
  END IF;

  INSERT INTO public.fusions(fluor_id, tag_id)
  VALUES (fid, tid)
  ON CONFLICT DO NOTHING;

  SELECT id INTO existing
  FROM public.fusions
  WHERE fluor_id=fid
    AND ((tid IS NULL AND tag_id IS NULL) OR tag_id=tid)
  LIMIT 1;

  RETURN existing;
END
$$;

DROP VIEW IF EXISTS public.v_rnas CASCADE;
CREATE VIEW public.v_rnas AS
WITH jf AS (
  SELECT
    j.rna_id,
    f.id AS fusion_id,
    fl.fluor_code,
    tg.tag_code
  FROM public.join_rna_fusions j
  JOIN public.fusions f ON f.id=j.fusion_id
  JOIN public.fluors fl ON fl.id=f.fluor_id
  LEFT JOIN public.tags tg ON tg.id=f.tag_id
),
agg AS (
  SELECT
    rna_id,
    (SELECT string_agg(s.fluor_code, ', ' ORDER BY s.fluor_code)
       FROM (SELECT DISTINCT fluor_code FROM jf x WHERE x.rna_id=jf.rna_id) s) AS fluors,
    (SELECT COALESCE(string_agg(s.tag_code, ', ' ORDER BY s.tag_code),'')
       FROM (SELECT DISTINCT tag_code FROM jf x WHERE x.rna_id=jf.rna_id AND x.tag_code IS NOT NULL) s) AS tags
  FROM jf
  GROUP BY rna_id
)
SELECT
  r.rna_code,
  r.nickname,
  r.notes,
  COALESCE(agg.fluors,'') AS fluors,
  COALESCE(agg.tags,'')   AS tags,
  r.created_at
FROM public.rnas r
LEFT JOIN agg ON agg.rna_id=r.id;

COMMIT;
