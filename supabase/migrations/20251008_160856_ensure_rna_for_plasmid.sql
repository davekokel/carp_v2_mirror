BEGIN;

-- helper: ensure RNA exists for a plasmid (suffix defaults to 'RNA')
CREATE OR REPLACE FUNCTION public.ensure_rna_for_plasmid(
  p_plasmid_code text,
  p_suffix       text DEFAULT 'RNA',
  p_name         text DEFAULT NULL,
  p_created_by   text DEFAULT NULL,
  p_notes        text DEFAULT NULL
)
RETURNS TABLE (rna_id uuid, rna_code text)
LANGUAGE plpgsql
AS $$
DECLARE
  v_plasmid_id uuid;
  v_code text;
BEGIN
  -- find plasmid
  SELECT id_uuid INTO v_plasmid_id
  FROM public.plasmids WHERE code = p_plasmid_code LIMIT 1;
  IF v_plasmid_id IS NULL THEN
    RAISE EXCEPTION 'ensure_rna_for_plasmid: plasmid code % not found', p_plasmid_code;
  END IF;

  v_code := p_plasmid_code || COALESCE(p_suffix,'RNA');

  -- upsert RNA
  INSERT INTO public.rnas(code, name, source_plasmid_id, created_by, notes)
  VALUES (v_code, COALESCE(p_name, v_code), v_plasmid_id, p_created_by, p_notes)
  ON CONFLICT (code) DO UPDATE
    SET name              = COALESCE(EXCLUDED.name, public.rnas.name),
        source_plasmid_id = COALESCE(EXCLUDED.source_plasmid_id, public.rnas.source_plasmid_id),
        created_by        = COALESCE(EXCLUDED.created_by, public.rnas.created_by),
        notes             = COALESCE(EXCLUDED.notes, public.rnas.notes)
  RETURNING id_uuid, code INTO rna_id, rna_code;

  RETURN NEXT;
END;
$$;

COMMIT;
