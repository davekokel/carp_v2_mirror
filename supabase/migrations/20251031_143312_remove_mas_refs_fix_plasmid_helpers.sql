-- 1) Drop any triggers whose function body mentions public.mas (legacy)
DO $$
DECLARE
  r record;
BEGIN
  FOR r IN
    SELECT n.nspname AS schema_name, c.relname AS table_name, t.tgname AS trigger_name
    FROM pg_trigger t
    JOIN pg_proc p      ON p.oid = t.tgfoid
    JOIN pg_class c     ON c.oid = t.tgrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE NOT t.tgisinternal
      AND pg_get_functiondef(p.oid) ILIKE '%public.mas%'
  LOOP
    EXECUTE format('DROP TRIGGER IF EXISTS %I ON %I.%I', r.trigger_name, r.schema_name, r.table_name);
  END LOOP;
END $$;

-- 2) Replace legacy ensure_* helpers to upsert into public.plasmids (no mas)
CREATE OR REPLACE FUNCTION public.ensure_ma_for_plasmid(
  p_code text,
  p_name text,
  p_created_by text,
  p_notes text
) RETURNS text
LANGUAGE plpgsql
AS $$
DECLARE out_code text;
BEGIN
  INSERT INTO public.plasmids (code, name, created_by, notes)
  VALUES (p_code, COALESCE(NULLIF(p_name,''), p_code), NULLIF(p_created_by,''), NULLIF(p_notes,''))
  ON CONFLICT (code) DO UPDATE
    SET name       = COALESCE(EXCLUDED.name, public.plasmids.name),
        created_by = COALESCE(EXCLUDED.created_by, public.plasmids.created_by),
        notes      = COALESCE(EXCLUDED.notes, public.plasmids.notes)
  RETURNING code INTO out_code;
  RETURN out_code;
END
$$;

-- Optional common variant used by some callers; keeps extra fields in sync.
CREATE OR REPLACE FUNCTION public.ensure_ma_for_plasmid(
  p_code text,
  p_name text,
  p_nickname text,
  p_resistance text,
  p_supports_invitro_rna boolean,
  p_notes text,
  p_created_by text
) RETURNS text
LANGUAGE plpgsql
AS $$
DECLARE out_code text;
BEGIN
  INSERT INTO public.plasmids (code, name, nickname, resistance, supports_invitro_rna, notes, created_by)
  VALUES (p_code,
          COALESCE(NULLIF(p_name,''), p_code),
          NULLIF(p_nickname,''),
          NULLIF(p_resistance,''),
          COALESCE(p_supports_invitro_rna,false),
          NULLIF(p_notes,''),
          NULLIF(p_created_by,''))
  ON CONFLICT (code) DO UPDATE
    SET name                 = COALESCE(EXCLUDED.name, public.plasmids.name),
        nickname             = COALESCE(EXCLUDED.nickname, public.plasmids.nickname),
        resistance           = COALESCE(EXCLUDED.resistance, public.plasmids.resistance),
        supports_invitro_rna = EXCLUDED.supports_invitro_rna,
        notes                = COALESCE(EXCLUDED.notes, public.plasmids.notes),
        created_by           = COALESCE(EXCLUDED.created_by, public.plasmids.created_by)
  RETURNING code INTO out_code;
  RETURN out_code;
END
$$;
