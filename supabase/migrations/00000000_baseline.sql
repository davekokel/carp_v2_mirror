SET search_path = public;

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE public.fish (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  fish_code     text UNIQUE NOT NULL,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.tanks (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tank_code     text UNIQUE NOT NULL,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.fish_tank_memberships (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  fish_id       uuid NOT NULL REFERENCES public.fish(id) ON DELETE CASCADE,
  tank_id       uuid NOT NULL REFERENCES public.tanks(id) ON DELETE CASCADE,
  since         timestamptz NOT NULL DEFAULT now(),
  until         timestamptz
);

CREATE TABLE public.tank_pairs (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tank_pair_code    text UNIQUE NOT NULL,
  mother_tank_id    uuid NOT NULL REFERENCES public.tanks(id) ON DELETE RESTRICT,
  father_tank_id    uuid NOT NULL REFERENCES public.tanks(id) ON DELETE RESTRICT,
  status            text NOT NULL DEFAULT 'selected',
  note              text,
  created_by        text,
  created_at        timestamptz NOT NULL DEFAULT now()
);

-- executed cross runs (keep name simple)
CREATE TABLE public.crosses (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tank_pair_code   text NOT NULL,
  cross_run_code   text UNIQUE,
  cross_date       date NOT NULL,
  run_nn           int,
  created_by       text,
  created_at       timestamptz NOT NULL DEFAULT now()
);

-- high-level clutch header (optional)
CREATE TABLE public.clutches (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  clutch_code    text UNIQUE,
  created_at     timestamptz NOT NULL DEFAULT now()
);

-- concrete clutches from a cross
CREATE TABLE public.clutch_instances (
  id                        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  clutch_instance_code      text UNIQUE,
  cross_instance_id         uuid REFERENCES public.crosses(id) ON DELETE CASCADE,
  tank_pair_code            text,
  clutch_genotype_pretty    text,
  created_at                timestamptz NOT NULL DEFAULT now()
);

-- generic materials registry (plasmids only for now)
CREATE TABLE public.plasmids (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code        text UNIQUE NOT NULL,
  name        text NOT NULL,
  nickname    text,
  created_at  timestamptz NOT NULL DEFAULT now(),
  created_by  text
);

-- fluors/tags/fusions for later resolution
CREATE TABLE public.fluors (
  fluor_code  text PRIMARY KEY,
  fluor_name  text NOT NULL
);
CREATE TABLE public.tags (
  tag_code    text PRIMARY KEY,
  tag_name    text NOT NULL
);
CREATE TABLE public.fusions (
  fusion_code  text PRIMARY KEY,
  fusion_name  text NOT NULL,
  fluor_code   text REFERENCES public.fluors(fluor_code),
  tag_code     text REFERENCES public.tags(tag_code)
);
CREATE TABLE public.plasmid_fusions (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  plasmid_code  text NOT NULL,
  fusion_code   text NOT NULL,
  position      int,
  created_at    timestamptz NOT NULL DEFAULT now()
);

-- link: clutch_instance ↔ material (generic; resolves via view later)
CREATE TABLE public.clutch_materials (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  clutch_instance_id uuid NOT NULL REFERENCES public.clutch_instances(id) ON DELETE CASCADE,
  material_type      text NOT NULL,         -- 'plasmid' for now
  material_code      text NOT NULL,         -- e.g., plasmid code
  material_name      text,
  notes              text,
  created_by         text,
  created_at         timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uq_clutch_materials_expr
  ON public.clutch_materials (clutch_instance_id, lower(coalesce(material_type,'')), lower(coalesce(material_code,'')));

-- genotype / allele bits (minimal stubs)
CREATE TABLE public.transgenes (
  transgene_base_code text PRIMARY KEY,
  created_at          timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE public.transgene_alleles (
  transgene_base_code text NOT NULL REFERENCES public.transgenes(transgene_base_code) ON DELETE CASCADE,
  allele_number       int  NOT NULL,
  PRIMARY KEY (transgene_base_code, allele_number)
);
CREATE TABLE public.transgene_allele_registry (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  transgene_base_code text NOT NULL,
  allele_number       int NOT NULL,
  issued_at           timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE public.fish_transgene_alleles (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  fish_id             uuid NOT NULL REFERENCES public.fish(id) ON DELETE CASCADE,
  transgene_base_code text NOT NULL,
  allele_number       int NOT NULL,
  zygosity            text,
  UNIQUE (fish_id, transgene_base_code, allele_number)
);

-- ops/history/light counters
CREATE TABLE public.tank_status_history (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tank_id     uuid NOT NULL REFERENCES public.tanks(id) ON DELETE CASCADE,
  status      text NOT NULL,
  changed_at  timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE public.fish_year_counters (
  year int PRIMARY KEY,
  next int NOT NULL
);

-- simple labels
CREATE TABLE public.label_jobs (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  kind        text NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE public.label_items (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  job_id      uuid NOT NULL REFERENCES public.label_jobs(id) ON DELETE CASCADE,
  payload     jsonb NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now()
);

-- mounts/containers stubs
CREATE TABLE public.containers (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  label       text,
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE public.mounts (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  mount_code  text UNIQUE,
  created_at  timestamptz NOT NULL DEFAULT now()
);
