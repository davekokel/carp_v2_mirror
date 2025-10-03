DO $MAIN$
DECLARE
  fish_exists boolean;
  treat_exists boolean;
  treat_pk_col text;
  treat_pk_type text;
  ft_col_type   text;
  types_match boolean;
BEGIN
  -- enums
  PERFORM 1 FROM pg_type WHERE typname='treatment_route';
  IF NOT FOUND THEN
    EXECUTE 'CREATE TYPE treatment_route AS ENUM (''bath'',''injection'',''feed'',''other'')';
  END IF;

  PERFORM 1 FROM pg_type WHERE typname='treatment_unit';
  IF NOT FOUND THEN
    EXECUTE 'CREATE TYPE treatment_unit AS ENUM (''µM'',''mM'',''nM'',''mg/L'',''µg/mL'',''%'',''other'')';
  END IF;

  -- protocols
  EXECUTE '
    CREATE TABLE IF NOT EXISTS public.treatment_protocols (
      protocol_code text PRIMARY KEY,
      display_name  text NOT NULL,
      description   text
    )';

  -- treatments (shape may vary across envs; don't assume PK name/type)
  IF to_regclass('public.treatments') IS NULL THEN
    EXECUTE '
      CREATE TABLE public.treatments (
        treatment_type text,
        display_name   text,
        route          treatment_route,
        protocol_code  text REFERENCES public.treatment_protocols(protocol_code),
        notes          text
      )';
  END IF;

  -- fish_treatments (create without FKs first)
  EXECUTE '
    CREATE TABLE IF NOT EXISTS public.fish_treatments (
      id_uuid        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      fish_id        uuid NOT NULL,
      treatment_id   uuid NOT NULL,
      applied_at     timestamptz,
      ended_at       timestamptz,
      dose           numeric,
      unit           treatment_unit,
      vehicle        text,
      batch_label    text,
      created_at     timestamptz NOT NULL DEFAULT now(),
      created_by     text
    )';

  -- FK → fish (only if fish exists)
  fish_exists := (to_regclass('public.fish') IS NOT NULL);
  IF fish_exists AND NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname='fish_treatments_fish_fk'
  ) THEN
    EXECUTE '
      ALTER TABLE public.fish_treatments
      ADD CONSTRAINT fish_treatments_fish_fk
      FOREIGN KEY (fish_id) REFERENCES public.fish(id_uuid) ON DELETE CASCADE';
  END IF;

  -- FK → treatments (only when single-column PK exists and types match)
  treat_exists := (to_regclass('public.treatments') IS NOT NULL);
  IF treat_exists AND NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname='fish_treatments_treatment_fk'
  ) THEN
    SELECT a.attname::text, format_type(a.atttypid,a.atttypmod)::text
    INTO treat_pk_col, treat_pk_type
    FROM pg_constraint c
    JOIN pg_class t ON t.oid=c.conrelid
    JOIN pg_namespace n ON n.oid=t.relnamespace
    JOIN LATERAL unnest(c.conkey) AS k(attnum) ON TRUE
    JOIN pg_attribute a ON a.attrelid=t.oid AND a.attnum=k.attnum
    WHERE n.nspname='public' AND t.relname='treatments' AND c.contype='p'
    GROUP BY a.attname, a.atttypid, a.atttypmod, c.conkey
    HAVING array_length(c.conkey,1)=1
    LIMIT 1;

    SELECT format_type(a.atttypid,a.atttypmod)::text
    INTO ft_col_type
    FROM pg_attribute a
    JOIN pg_class t ON t.oid=a.attrelid
    JOIN pg_namespace n ON n.oid=t.relnamespace
    WHERE n.nspname='public' AND t.relname='fish_treatments' AND a.attname='treatment_id';

    types_match := (treat_pk_col IS NOT NULL) AND (treat_pk_type = ft_col_type);

    IF types_match THEN
      EXECUTE format(
        'ALTER TABLE public.fish_treatments
         ADD CONSTRAINT fish_treatments_treatment_fk
         FOREIGN KEY (treatment_id) REFERENCES public.treatments(%I)',
        treat_pk_col
      );
    END IF;
    -- else: skip FK; types incompatible (e.g., treatments uses text code, fish_treatments uses uuid)
  END IF;
END
$MAIN$;
