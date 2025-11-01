DO $$
DECLARE
  trash text := 'trash_carp';
  owner_oid oid := (SELECT oid FROM pg_roles WHERE rolname = current_user);
  rec record;
  core_patterns text[] := ARRAY[
    '%fish%','%tank%','%cross%','%clutch%','%treatment%','%plasmid%',
    '%label%','%container%','%transgene%','%allele%','%year_counter%',
    '%pair%','%run%','%annotation%','%seed%','mount%','genotype%'
  ];
BEGIN
  EXECUTE format('create schema if not exists %I', trash);

  FOR rec IN
    SELECT n.nspname AS schema_name, c.relname AS table_name
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE c.relkind IN ('r','p')
      AND n.nspname = 'public'
      AND c.relowner = owner_oid
      AND NOT (lower(c.relname) LIKE ANY (core_patterns))
  LOOP
    IF to_regclass(format('%I.%I', trash, rec.table_name)) IS NULL THEN
      EXECUTE format('ALTER TABLE %I.%I SET SCHEMA %I', rec.schema_name, rec.table_name, trash);
    END IF;
  END LOOP;
END $$;
