BEGIN;

CREATE OR REPLACE VIEW public.vw_plasmids_overview AS
SELECT
  p.id_uuid,
  p.code,
  p.name,
  p.nickname,
  p.fluors,
  p.resistance,
  p.supports_invitro_rna,
  p.created_by,
  p.notes,
  p.created_at,
  r.id_uuid        AS rna_id,
  r.code           AS rna_code,
  r.name           AS rna_name,
  r.source_plasmid_id
FROM public.plasmids p
LEFT JOIN public.rnas r
  ON r.source_plasmid_id = p.id_uuid
ORDER BY p.code;

COMMIT;
