DO $$
DECLARE
  fish_pk_col   text;
  plasmid_pk_col text;
BEGIN
  -- pick fish PK column ('id' preferred, fallback 'id_uuid')
  fish_pk_col := CASE
    WHEN EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema='public' AND table_name='fish' AND column_name='id'
    ) THEN 'id'
    WHEN EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema='public' AND table_name='fish' AND column_name='id_uuid'
    ) THEN 'id_uuid'
    ELSE NULL
  END;

  -- pick plasmids PK column ('id' preferred, fallback 'id_uuid')
  plasmid_pk_col := CASE
    WHEN EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema='public' AND table_name='plasmids' AND column_name='id'
    ) THEN 'id'
    WHEN EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema='public' AND table_name='plasmids' AND column_name='id_uuid'
    ) THEN 'id_uuid'
    ELSE NULL
  END;

  -- 1) table (no FKs yet)
  IF to_regclass('public.injected_plasmid_treatments') IS NULL THEN
    EXECUTE '
      CREATE TABLE public.injected_plasmid_treatments (
        id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        fish_id     uuid NOT NULL,
        plasmid_id  uuid NOT NULL,
        amount      numeric NULL,
        units       text    NULL,
        at_time     timestamptz NULL,
        note        text    NULL
      )';
  END IF;

  -- 2) natural de-dupe index
  IF NOT EXISTS (
    SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname='public' AND c.relname='uq_ipt_natural'
  ) THEN
    EXECUTE '
      CREATE UNIQUE INDEX uq_ipt_natural
        ON public.injected_plasmid_treatments(fish_id, plasmid_id, at_time, amount, units, note)';
  END IF;

  -- 3) FK → fish (if we could determine PK col)
  IF fish_pk_col IS NOT NULL
     AND NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_ipt_fish') THEN
    EXECUTE format(
      'ALTER TABLE public.injected_plasmid_treatments
         ADD CONSTRAINT fk_ipt_fish
         FOREIGN KEY (fish_id) REFERENCES public.fish(%I) ON DELETE CASCADE',
      fish_pk_col
    );
  END IF;

  -- 4) FK → plasmids (if table exists and PK col found)
  IF to_regclass('public.plasmids') IS NOT NULL
     AND plasmid_pk_col IS NOT NULL
     AND NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_ipt_plasmid') THEN
    EXECUTE format(
      'ALTER TABLE public.injected_plasmid_treatments
         ADD CONSTRAINT fk_ipt_plasmid
         FOREIGN KEY (plasmid_id) REFERENCES public.plasmids(%I) ON DELETE RESTRICT',
      plasmid_pk_col
    );
  END IF;
END
$$;
