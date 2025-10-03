DO $MAIN$
DECLARE
  fish_pk_col  text;
  fish_pk_type text;
BEGIN
  -- Detect single-column PK on public.fish (name + type)
  SELECT a.attname::text, format_type(a.atttypid, a.atttypmod)::text
  INTO fish_pk_col, fish_pk_type
  FROM pg_constraint c
  JOIN pg_class t        ON t.oid = c.conrelid
  JOIN pg_namespace n    ON n.oid = t.relnamespace
  JOIN LATERAL unnest(c.conkey) k(attnum) ON TRUE
  JOIN pg_attribute a    ON a.attrelid = t.oid AND a.attnum = k.attnum
  WHERE n.nspname='public' AND t.relname='fish' AND c.contype='p'
  GROUP BY a.attname, a.atttypid, a.atttypmod, c.conkey
  HAVING array_length(c.conkey,1)=1
  LIMIT 1;

  -- 1) Create IPT table without FKs first
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

  -- 2) Natural de-dupe index (idempotent)
  IF NOT EXISTS (
    SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname='public' AND c.relname='uq_ipt_natural'
  ) THEN
    EXECUTE '
      CREATE UNIQUE INDEX uq_ipt_natural
        ON public.injected_plasmid_treatments(fish_id, plasmid_id, at_time, amount, units, note)';
  END IF;

  -- 3) Add FK → plasmids if table/column exists
  IF to_regclass('public.plasmids') IS NOT NULL
     AND EXISTS (
       SELECT 1 FROM information_schema.columns
       WHERE table_schema=''public'' AND table_name=''plasmids'' AND column_name=''id_uuid''
     )
     AND NOT EXISTS (
       SELECT 1 FROM pg_constraint WHERE conname=''ipt_plasmid_fk''
     )
  THEN
    EXECUTE '
      ALTER TABLE public.injected_plasmid_treatments
      ADD CONSTRAINT ipt_plasmid_fk
      FOREIGN KEY (plasmid_id) REFERENCES public.plasmids(id_uuid) ON DELETE RESTRICT';
  END IF;

  -- 4) Add FK → fish only if we found a single-column PK and it's uuid
  IF fish_pk_col IS NOT NULL
     AND fish_pk_type = 'uuid'
     AND NOT EXISTS (
       SELECT 1 FROM pg_constraint WHERE conname=''ipt_fish_fk''
     )
  THEN
    EXECUTE format(
      'ALTER TABLE public.injected_plasmid_treatments
         ADD CONSTRAINT ipt_fish_fk
         FOREIGN KEY (fish_id) REFERENCES public.fish(%I) ON DELETE CASCADE',
      fish_pk_col
    );
  END IF;
END
$MAIN$;
