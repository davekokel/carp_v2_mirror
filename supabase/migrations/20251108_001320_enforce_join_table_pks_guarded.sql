BEGIN;
/*
Guarded PK enforcement for current join tables only.
It will quietly skip any table that doesn't exist.
*/

DO $$
DECLARE
  rec RECORD;
BEGIN
  -- Define the join tables and their composite PK columns
  FOR rec IN
    SELECT *
    FROM (VALUES
      ('join_plasmid_fusions',        'plasmid_id,fusion_id',          'pk_jpf'),
      ('join_rna_fusions',            'rna_id,fusion_id',               'pk_jrf'),
      ('join_crispr_fusions',         'knockin_id,fusion_id',           'pk_jcf'),
      ('join_ft_dyes',                'ft_id,dye_id',                   'pk_jftd'),
      ('join_ft_fusions',             'ft_id,fusion_id',                'pk_jftf'),
      ('join_fish_treatments_fluorescent','fish_id,ft_id',              'pk_jftf_fish_ft'),
      ('join_fish_transgene_alleles', 'fish_id,transgene_base_code,allele_number','pk_jfta')
    ) AS t(tbl, cols, pkname)
  LOOP
    -- skip if table doesn't exist
    IF to_regclass('public.'||rec.tbl) IS NULL THEN
      CONTINUE;
    END IF;

    -- skip if a primary key already exists
    IF EXISTS (
      SELECT 1
      FROM pg_constraint
      WHERE conrelid = ('public.'||rec.tbl)::regclass
        AND contype  = 'p'
    ) THEN
      CONTINUE;
    END IF;

    -- add the primary key
    EXECUTE format('ALTER TABLE public.%I ADD CONSTRAINT %I PRIMARY KEY (%s);',
                   rec.tbl, rec.pkname, rec.cols);
  END LOOP;
END$$;

COMMIT;
