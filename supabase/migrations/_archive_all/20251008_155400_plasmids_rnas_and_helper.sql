BEGIN;

-- 1) plasmids: flag + uniqueness
ALTER TABLE public.plasmids
ADD COLUMN IF NOT EXISTS supports_invitro_rna boolean NOT NULL DEFAULT false;
CREATE UNIQUE INDEX IF NOT EXISTS uq_plasmids_code ON public.plasmids (code);

-- 2) rnas table
CREATE TABLE IF NOT EXISTS public.rnas (
    id_uuid uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    code text UNIQUE NOT NULL,
    name text,
    source_plasmid_id uuid REFERENCES public.plasmids (id_uuid) ON DELETE SET NULL,
    created_by text,
    notes text,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_rnas_source_plasmid ON public.rnas (source_plasmid_id);

-- 3) helper: ensure RNA exists for a plasmid (suffix defaults to 'RNA')
CREATE OR REPLACE FUNCTION public.ensure_rna_for_plasmid(
    p_plasmid_code text,
    p_suffix text DEFAULT 'RNA',
    p_name text DEFAULT null,
    p_created_by text DEFAULT null,
    p_notes text DEFAULT null
)
RETURNS TABLE (rna_id uuid, rna_code text)
LANGUAGE plpgsql
AS $$
DECLARE
  v_plasmid_id uuid;
  v_code text;
BEGIN
  SELECT id_uuid INTO v_plasmid_id
  FROM public.plasmids WHERE code = p_plasmid_code LIMIT 1;
  IF v_plasmid_id IS NULL THEN
    RAISE EXCEPTION 'ensure_rna_for_plasmid: plasmid code % not found', p_plasmid_code;
  END IF;

  v_code := p_plasmid_code || COALESCE(p_suffix,'RNA');

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

-- 4) unified materials view for UI (optional but handy)
CREATE OR REPLACE VIEW public.vw_treatment_materials AS
SELECT
    'plasmid'::text AS material_type,
    p.id_uuid AS material_id,
    p.code AS material_code,
    p.name AS material_name,
    null::uuid AS source_plasmid_id,
    p.supports_invitro_rna,
    p.created_at
FROM public.plasmids AS p
UNION ALL
SELECT
    'rna'::text,
    r.id_uuid,
    r.code,
    r.name,
    r.source_plasmid_id,
    true,
    r.created_at
FROM public.rnas AS r;

COMMIT;
