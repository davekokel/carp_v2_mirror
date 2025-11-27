BEGIN;

CREATE TABLE public.fish_groups (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  genotype_key text NOT NULL UNIQUE,
  nickname     text,
  created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.join_fish_group_alleles (
  fish_group_id uuid NOT NULL REFERENCES public.fish_groups(id) ON DELETE CASCADE,
  construct_id  uuid NOT NULL REFERENCES public.constructs(id) ON DELETE RESTRICT,
  allele_number integer NOT NULL,
  PRIMARY KEY (fish_group_id, construct_id, allele_number)
);

ALTER TABLE public.fish_lines
  ADD COLUMN fish_group_id uuid REFERENCES public.fish_groups(id);

CREATE INDEX ON public.fish_lines (fish_group_id);

COMMIT;
