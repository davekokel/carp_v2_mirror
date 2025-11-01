-- Replace the legacy helper so callers stop writing to public.mas
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
  VALUES (p_code, p_name, NULLIF(p_nickname,''), NULLIF(p_resistance,''), COALESCE(p_supports_invitro_rna,false), NULLIF(p_notes,''), NULLIF(p_created_by,''))
  ON CONFLICT (code) DO UPDATE
    SET name                  = EXCLUDED.name,
        nickname              = EXCLUDED.nickname,
        resistance            = EXCLUDED.resistance,
        supports_invitro_rna  = EXCLUDED.supports_invitro_rna,
        notes                 = EXCLUDED.notes,
        created_by            = COALESCE(EXCLUDED.created_by, public.plasmids.created_by)
  RETURNING code INTO out_code;

  RETURN out_code;
END
$$;
