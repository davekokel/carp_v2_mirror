ALTER TABLE ONLY public.fish_seed_batches_map
  DROP CONSTRAINT IF EXISTS fk_fsbm_fish;

ALTER TABLE ONLY public.fish_seed_batches_map
  ADD CONSTRAINT fk_fsbm_fish
  FOREIGN KEY (fish_id) REFERENCES public.fish(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE public.fish DROP COLUMN IF EXISTS id_uuid;
