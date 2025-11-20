BEGIN;

CREATE TABLE IF NOT EXISTS public.join_fish_transgene_alleles (
  fish_id             uuid NOT NULL,
  transgene_base_code text NOT NULL,
  allele_number       integer NOT NULL,
  zygosity            text,
  created_at          timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT fk_jfta_fish
    FOREIGN KEY (fish_id)
    REFERENCES public.fish_instance(id)
    ON UPDATE CASCADE
    ON DELETE CASCADE,
  CONSTRAINT fk_jfta_allele
    FOREIGN KEY (transgene_base_code, allele_number)
    REFERENCES public.transgene_alleles(transgene_base_code, allele_number)
    ON UPDATE CASCADE
    ON DELETE RESTRICT,
  CONSTRAINT jfta_pkey
    PRIMARY KEY (fish_id, transgene_base_code, allele_number)
);

COMMIT;
