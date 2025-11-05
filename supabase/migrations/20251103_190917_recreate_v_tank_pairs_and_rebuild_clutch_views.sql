BEGIN;

DROP VIEW IF EXISTS public.v_clutch_instances_clean_compat;
DROP VIEW IF EXISTS public.v_clutch_instances_clean;
DROP VIEW IF EXISTS public.v_clutch_instances_resolved_compat;
DROP VIEW IF EXISTS public.v_clutch_instances;
DROP VIEW IF EXISTS public.v_tank_pairs;

DO $$
DECLARE
  pair_code    text;
  male_col     text;
  female_col   text;
  created_col  text;

  male_expr    text;
  female_expr  text;
  created_expr text;

  sql          text;
BEGIN
  SELECT column_name INTO pair_code
  FROM information_schema.columns
  WHERE table_schema='public' AND table_name='tank_pairs'
    AND column_name IN ('tank_pair_code','code','pair_code')
  ORDER BY CASE column_name WHEN 'tank_pair_code' THEN 1 WHEN 'code' THEN 2 WHEN 'pair_code' THEN 3 ELSE 9 END
  LIMIT 1;

  SELECT column_name INTO male_col
  FROM information_schema.columns
  WHERE table_schema='public' AND table_name='tank_pairs'
    AND column_name IN ('tank_code_male','male_tank_code','tank_male_code','male_code')
  ORDER BY CASE column_name WHEN 'tank_code_male' THEN 1 WHEN 'male_tank_code' THEN 2 WHEN 'tank_male_code' THEN 3 WHEN 'male_code' THEN 4 ELSE 9 END
  LIMIT 1;

  SELECT column_name INTO female_col
  FROM information_schema.columns
  WHERE table_schema='public' AND table_name='tank_pairs'
    AND column_name IN ('tank_code_female','female_tank_code','tank_female_code','female_code')
  ORDER BY CASE column_name WHEN 'tank_code_female' THEN 1 WHEN 'female_tank_code' THEN 2 WHEN 'tank_female_code' THEN 3 WHEN 'female_code' THEN 4 ELSE 9 END
  LIMIT 1;

  SELECT column_name INTO created_col
  FROM information_schema.columns
  WHERE table_schema='public' AND table_name='tank_pairs'
    AND column_name IN ('created_at','created','inserted_at')
  ORDER BY CASE column_name WHEN 'created_at' THEN 1 WHEN 'created' THEN 2 WHEN 'inserted_at' THEN 3 ELSE 9 END
  LIMIT 1;

  IF pair_code IS NULL THEN
    RAISE EXCEPTION 'tank_pairs needs a pair code column (tank_pair_code/code/pair_code)';
  END IF;

  IF male_col IS NOT NULL THEN
    male_expr := format('tp.%I', male_col);
  ELSE
    male_expr := 'NULL::text';
  END IF;

  IF female_col IS NOT NULL THEN
    female_expr := format('tp.%I', female_col);
  ELSE
    female_expr := 'NULL::text';
  END IF;

  IF created_col IS NOT NULL THEN
    created_expr := format('tp.%I', created_col);
  ELSE
    created_expr := 'NULL::timestamptz';
  END IF;

  sql := format($v$
    CREATE VIEW public.v_tank_pairs AS
    SELECT
      tp.%1$I AS tank_pair_code,
      %2$s    AS tank_code_male,
      %3$s    AS tank_code_female,
      %4$s    AS created_at
    FROM public.tank_pairs tp;
  $v$, pair_code, male_expr, female_expr, created_expr);

  EXECUTE sql;
END$$;

CREATE VIEW public.v_clutch_instances AS
SELECT clutch_id, clutch_code, clutch_genotype_pretty, clutch_instance_id, clutch_instance_code, created_at
FROM public.v_clutch_instances_base_resolved;

CREATE VIEW public.v_clutch_instances_clean AS
SELECT clutch_id, clutch_code,
       COALESCE(clutch_genotype_pretty,'') AS clutch_genotype_pretty,
       clutch_instance_id,
       COALESCE(clutch_instance_code,'')   AS clutch_instance_code,
       created_at
FROM public.v_clutch_instances;

CREATE VIEW public.v_clutch_instances_clean_compat AS
SELECT clutch_id, clutch_code, clutch_genotype_pretty, clutch_instance_id, clutch_instance_code, created_at
FROM public.v_clutch_instances_clean;

CREATE VIEW public.v_clutch_instances_resolved_compat AS
SELECT clutch_id, clutch_code, clutch_genotype_pretty, clutch_instance_id, clutch_instance_code, created_at
FROM public.v_clutch_instances;

COMMIT;
