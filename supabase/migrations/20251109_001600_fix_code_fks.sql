BEGIN;
/*
Create UNIQUE(code) indexes where the column exists.
This avoids legacy columns like fusion_code and plays nice with your cleaned schema.
*/
DO $$
DECLARE rec record;
BEGIN
  FOR rec IN
    SELECT * FROM (VALUES
      ('dyes','dye_code'),
      ('fluors','fluor_code'),
      ('tags','tag_code'),
      ('transgenes','transgene_base_code'),
      ('plasmids','code'),
      ('rnas','rna_code'),
      ('treatments','treat_code'),
      ('treatments_chemical','ct_code'),
      ('treatments_fluorescent','ft_code'),
      ('treatments_physical','pt_code'),
      ('fish','fish_code'),
      ('tanks','tank_code'),
      ('tank_pairs','tank_pair_code'),
      ('plates','plate_code'),
      ('treated_clutches','treated_clutch_code'),
      ('clutch_instances','clutch_instance_code'),
      ('crosses','cross_run_code')
    ) AS t(tbl,col)
  LOOP
    IF EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema='public' AND table_name=rec.tbl AND column_name=rec.col
    ) THEN
      EXECUTE format(
        'CREATE UNIQUE INDEX IF NOT EXISTS %I ON public.%I(%I);',
        'uq_'||rec.tbl||'_'||rec.col, rec.tbl, rec.col
      );
    END IF;
  END LOOP;
END$$;
COMMIT;
