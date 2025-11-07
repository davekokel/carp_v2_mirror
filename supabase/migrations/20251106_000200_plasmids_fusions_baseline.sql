BEGIN;

CREATE TABLE IF NOT EXISTS public.plasmids (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code                  text UNIQUE NOT NULL,
  name                  text NOT NULL DEFAULT '',
  nickname              text,
  resistance            text,
  supports_invitro_rna  boolean NOT NULL DEFAULT false,
  notes                 text,
  created_by            text,
  created_at            timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.fusions (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  fusion_code  text UNIQUE NOT NULL,
  fusion_name  text,
  fluor_id     uuid REFERENCES public.fluors(id),
  tag_id       uuid REFERENCES public.tags(id),
  created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.join_plasmid_fusions (
  plasmid_id   uuid NOT NULL REFERENCES public.plasmids(id) ON DELETE CASCADE,
  fusion_id    uuid NOT NULL REFERENCES public.fusions(id)  ON DELETE CASCADE,
  created_at   timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (plasmid_id, fusion_id)
);

CREATE OR REPLACE VIEW public.v_plasmids_rich AS
WITH links AS (
  SELECT
    p.id         AS plasmid_id,
    p.code       AS plasmid_code,
    f.fusion_code,
    COALESCE(fl.fluor_name, fl.fluor_code, '') AS fluor_name,
    COALESCE(tg.tag_name,   tg.tag_code,   '') AS tag_name
  FROM public.plasmids p
  LEFT JOIN public.join_plasmid_fusions j ON j.plasmid_id = p.id
  LEFT JOIN public.fusions f              ON f.id = j.fusion_id
  LEFT JOIN public.fluors fl ON fl.id = f.fluor_id
  LEFT JOIN public.tags   tg ON tg.id = f.tag_id
),
agg AS (
  SELECT
    plasmid_id,
    plasmid_code,
    COALESCE(NULLIF(string_agg(DISTINCT fusion_code, ', '), ''), '') AS fusion_names,
    COALESCE(NULLIF(string_agg(DISTINCT fluor_name,  ', '), ''), '') AS fluor_names,
    COALESCE(NULLIF(string_agg(DISTINCT tag_name,    ', '), ''), '') AS tag_names
  FROM links
  GROUP BY plasmid_id, plasmid_code
)
SELECT
  p.id                        AS plasmid_id,
  p.code                      AS plasmid_code,
  p.name                      AS plasmid_name,
  COALESCE(p.nickname,'')     AS nickname,
  COALESCE(a.fluor_names,'')  AS fluor_names,
  COALESCE(a.tag_names,'')    AS tag_names,
  COALESCE(a.fusion_names,'') AS fusion_names,
  COALESCE(p.resistance,'')   AS resistance,
  p.supports_invitro_rna      AS supports_invitro_rna,
  p.notes,
  p.created_by,
  p.created_at
FROM public.plasmids p
LEFT JOIN agg a ON a.plasmid_id = p.id;

COMMIT;
