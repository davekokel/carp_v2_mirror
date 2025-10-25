-- Idempotent link tables that adapt to either id/uuid PKs or code text uniques.

DO $$
DECLARE
  has_plasmid_id boolean := EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='plasmids' AND column_name='id'
  );
  has_plasmid_code boolean := EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='plasmids' AND column_name='plasmid_code'
  );
  has_rna_id boolean := EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='rnas' AND column_name='id'
  );
  has_rna_code boolean := EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='rnas' AND column_name='rna_code'
  );
BEGIN
  IF to_regclass('public.fish') IS NULL THEN
    RAISE NOTICE 'Skipping wide_links: public.fish missing';
    RETURN;
  END IF;

  -- ========= Plasmids ⇄ Fish =========
  IF to_regclass('public.plasmids') IS NOT NULL THEN
    IF to_regclass('public.fish_plasmids') IS NULL THEN
      IF has_plasmid_id THEN
        EXECUTE '
          CREATE TABLE public.fish_plasmids(
            fish_id    uuid REFERENCES public.fish(id) ON DELETE CASCADE,
            plasmid_id uuid REFERENCES public.plasmids(id) ON DELETE RESTRICT,
            PRIMARY KEY (fish_id, plasmid_id)
          )';
      ELSIF has_plasmid_code THEN
        EXECUTE '
          CREATE TABLE public.fish_plasmids(
            fish_id      uuid REFERENCES public.fish(id) ON DELETE CASCADE,
            plasmid_code text REFERENCES public.plasmids(plasmid_code) ON DELETE RESTRICT,
            PRIMARY KEY (fish_id, plasmid_code)
          )';
      ELSE
        RAISE NOTICE 'Skipping fish_plasmids: neither id nor plasmid_code present on plasmids';
      END IF;
    END IF;
  END IF;

  -- ========= RNAs ⇄ Fish =========
  IF to_regclass('public.rnas') IS NOT NULL THEN
    IF to_regclass('public.fish_rnas') IS NULL THEN
      IF has_rna_id THEN
        EXECUTE '
          CREATE TABLE public.fish_rnas(
            fish_id uuid REFERENCES public.fish(id) ON DELETE CASCADE,
            rna_id  uuid REFERENCES public.rnas(id) ON DELETE RESTRICT,
            PRIMARY KEY (fish_id, rna_id)
          )';
      ELSIF has_rna_code THEN
        EXECUTE '
          CREATE TABLE public.fish_rnas(
            fish_id  uuid REFERENCES public.fish(id) ON DELETE CASCADE,
            rna_code text REFERENCES public.rnas(rna_code) ON DELETE RESTRICT,
            PRIMARY KEY (fish_id, rna_code)
          )';
      ELSE
        RAISE NOTICE 'Skipping fish_rnas: neither id nor rna_code present on rnas';
      END IF;
    END IF;
  END IF;

  -- ========= Optional dyes / fluors (only if those tables exist) =========
  IF to_regclass('public.dyes') IS NOT NULL AND to_regclass('public.fish_dyes') IS NULL THEN
    EXECUTE '
      CREATE TABLE public.fish_dyes(
        fish_id uuid REFERENCES public.fish(id) ON DELETE CASCADE,
        dye_name text REFERENCES public.dyes(name) ON DELETE RESTRICT,
        PRIMARY KEY (fish_id, dye_name)
      )';
  END IF;

  IF to_regclass('public.fluors') IS NOT NULL AND to_regclass('public.fish_fluors') IS NULL THEN
    EXECUTE '
      CREATE TABLE public.fish_fluors(
        fish_id uuid REFERENCES public.fish(id) ON DELETE CASCADE,
        fluor_name text REFERENCES public.fluors(name) ON DELETE RESTRICT,
        PRIMARY KEY (fish_id, fluor_name)
      )';
  END IF;
END
$$;
