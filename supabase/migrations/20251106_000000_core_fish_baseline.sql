BEGIN;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.fish (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  fish_code           text UNIQUE NOT NULL,
  nickname            text,
  dob                 date,
  genetic_background  text,
  line_building_stage text,
  identity_key        text,
  identity_hash       text,
  created_at          timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.transgenes (
  transgene_base_code text PRIMARY KEY,
  created_at          timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.transgene_alleles (
  transgene_base_code text NOT NULL REFERENCES public.transgenes(transgene_base_code) ON DELETE CASCADE,
  allele_number       int  NOT NULL,
  allele_nickname     text,
  allele_name         text,
  created_at          timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (transgene_base_code, allele_number)
);

CREATE TABLE IF NOT EXISTS public.join_fish_transgene_alleles (
  fish_id             uuid NOT NULL REFERENCES public.fish(id) ON DELETE CASCADE,
  transgene_base_code text NOT NULL REFERENCES public.transgenes(transgene_base_code) ON DELETE CASCADE,
  allele_number       int  NOT NULL,
  zygosity            text,
  created_at          timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (fish_id, transgene_base_code, allele_number)
);

CREATE TABLE IF NOT EXISTS public.fluorescent_treatments (
  ft_code     text PRIMARY KEY,
  ft_text     text NOT NULL DEFAULT '',
  created_by  text,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.fluors (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  fluor_code  text UNIQUE NOT NULL,
  fluor_name  text
);

CREATE TABLE IF NOT EXISTS public.tags (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tag_code    text UNIQUE NOT NULL,
  tag_name    text
);

CREATE TABLE IF NOT EXISTS public.dyes (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  dye_code    text UNIQUE NOT NULL,
  dye_name    text
);

CREATE TABLE IF NOT EXISTS public.ft_proteins (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ft_code     text NOT NULL REFERENCES public.fluorescent_treatments(ft_code) ON DELETE CASCADE,
  fluor_code  text NOT NULL REFERENCES public.fluors(fluor_code),
  tag_code    text REFERENCES public.tags(tag_code),
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_ft_proteins_ft_fluor_tag_norm
  ON public.ft_proteins (ft_code, (COALESCE(tag_code,'∅')), fluor_code);

CREATE TABLE IF NOT EXISTS public.ft_dyes (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ft_code     text NOT NULL REFERENCES public.fluorescent_treatments(ft_code) ON DELETE CASCADE,
  dye_code    text NOT NULL REFERENCES public.dyes(dye_code),
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_ft_dyes_ft_dye
  ON public.ft_dyes (ft_code, dye_code);

CREATE TABLE IF NOT EXISTS public.join_fish_fluorescent_treatments (
  fish_id       uuid NOT NULL REFERENCES public.fish(id) ON DELETE CASCADE,
  ft_code       text NOT NULL REFERENCES public.fluorescent_treatments(ft_code) ON DELETE CASCADE,
  allele_number text,
  zygosity      text,
  created_at    timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (fish_id, ft_code)
);
COMMIT;
