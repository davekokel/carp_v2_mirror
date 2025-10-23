BEGIN;

CREATE OR REPLACE VIEW public.v_plasmids
( id, code, name, nickname, fluors, resistance, supports_invitro_rna,
  created_by, notes, created_at, rna_id, rna_code, rna_name, source_plasmid_id ) AS
SELECT
  p.id,
  p.code,
  p.name,
  p.nickname,
  p.fluors,
  p.resistance,
  p.supports_invitro_rna,
  p.created_by,
  p.notes,
  p.created_at,
  r.id  AS rna_id,
  r.code AS rna_code,
  r.name AS rna_name,
  r.source_plasmid_id
FROM plasmids p
LEFT JOIN rnas r ON r.source_plasmid_id = p.id
ORDER BY p.code;

COMMIT;
