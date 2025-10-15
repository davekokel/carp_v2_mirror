-- Ensure fish.id is ready
ALTER TABLE public.fish ADD COLUMN IF NOT EXISTS id uuid;
UPDATE public.fish SET id = id_uuid WHERE id IS NULL;
ALTER TABLE public.fish ALTER COLUMN id SET NOT NULL;
ALTER TABLE public.fish ALTER COLUMN id SET DEFAULT gen_random_uuid();

-- 1) Drop all child FKs that currently depend on fish_pkey (on id_uuid)
ALTER TABLE ONLY public.cross_plans                DROP CONSTRAINT IF EXISTS cross_plans_father_fish_id_fkey;
ALTER TABLE ONLY public.cross_plans                DROP CONSTRAINT IF EXISTS cross_plans_mother_fish_id_fkey;
ALTER TABLE ONLY public.fish_tank_memberships      DROP CONSTRAINT IF EXISTS fish_tank_memberships_fish_id_fkey;
ALTER TABLE ONLY public.fish_transgene_alleles     DROP CONSTRAINT IF EXISTS fish_transgene_alleles_fish_id_fkey;
ALTER TABLE ONLY public.fish_seed_batches          DROP CONSTRAINT IF EXISTS fk_fsb_fish;
ALTER TABLE ONLY public.fish_seed_batches          DROP CONSTRAINT IF EXISTS fk_fsbm_fish;
ALTER TABLE ONLY public.injected_plasmid_treatments DROP CONSTRAINT IF EXISTS injected_plasmid_treatments_fish_id_fkey;
ALTER TABLE ONLY public.injected_plasmid_treatments DROP CONSTRAINT IF EXISTS fk_ipt_fish;
ALTER TABLE ONLY public.injected_rna_treatments    DROP CONSTRAINT IF EXISTS injected_rna_treatments_fish_id_fkey;
ALTER TABLE ONLY public.injected_rna_treatments    DROP CONSTRAINT IF EXISTS irt_fish_fk;
ALTER TABLE ONLY public.load_log_fish              DROP CONSTRAINT IF EXISTS load_log_fish_fish_id_fkey;

-- 2) Swap fish primary key to (id);
DO 28762
BEGIN
DECLARE pkname text;
BEGIN
  SELECT c.conname INTO pkname
  FROM pg_constraint c
  JOIN pg_class cl ON cl.oid=c.conrelid
  JOIN pg_namespace n ON n.oid=cl.relnamespace AND n.nspname='public'
  WHERE c.contype='p' AND cl.relname='fish';
  IF pkname IS NOT NULL THEN
    EXECUTE 'ALTER TABLE public.fish DROP CONSTRAINT '||quote_ident(pkname);
  END IF;
  EXECUTE 'ALTER TABLE public.fish ADD CONSTRAINT fish_pkey PRIMARY KEY (id)';
END;
END;
$$ LANGUAGE plpgsql;

-- 3) Drop transition bits and old column
ALTER TABLE public.fish DROP CONSTRAINT IF EXISTS fish_id_equals_id_uuid;
DROP INDEX IF EXISTS public.fish_id_key;
ALTER TABLE public.fish DROP COLUMN IF EXISTS id_uuid;

-- 4) Recreate child FKs pointing to fish(id)
ALTER TABLE ONLY public.cross_plans
  ADD CONSTRAINT cross_plans_father_fish_id_fkey
  FOREIGN KEY (father_fish_id) REFERENCES public.fish(id) ON DELETE RESTRICT;
ALTER TABLE ONLY public.cross_plans
  ADD CONSTRAINT cross_plans_mother_fish_id_fkey
  FOREIGN KEY (mother_fish_id) REFERENCES public.fish(id) ON DELETE RESTRICT;

ALTER TABLE ONLY public.fish_tank_memberships
  ADD CONSTRAINT fish_tank_memberships_fish_id_fkey
  FOREIGN KEY (fish_id) REFERENCES public.fish(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.fish_transgene_alleles
  ADD CONSTRAINT fish_transgene_alleles_fish_id_fkey
  FOREIGN KEY (fish_id) REFERENCES public.fish(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.fish_seed_batches
  ADD CONSTRAINT fk_fsb_fish
  FOREIGN KEY (fish_id) REFERENCES public.fish(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE ONLY public.injected_plasmid_treatments
  ADD CONSTRAINT injected_plasmid_treatments_fish_id_fkey
  FOREIGN KEY (fish_id) REFERENCES public.fish(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.injected_rna_treatments
  ADD CONSTRAINT injected_rna_treatments_fish_id_fkey
  FOREIGN KEY (fish_id) REFERENCES public.fish(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.load_log_fish
  ADD CONSTRAINT load_log_fish_fish_id_fkey
  FOREIGN KEY (fish_id) REFERENCES public.fish(id) ON DELETE CASCADE;
