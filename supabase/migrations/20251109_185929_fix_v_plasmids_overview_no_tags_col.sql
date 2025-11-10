BEGIN;

CREATE OR REPLACE VIEW public.v_plasmids_overview AS
WITH jf AS (
  SELECT
    p.id                       AS plasmid_id,
    p.code,
    p.name,
    COALESCE(p.nickname,'')    AS nickname,
    COALESCE(p.resistance,'')  AS resistance,
    COALESCE(p.supports_invitro_rna,false) AS supports_invitro_rna,
    p.created_at
  FROM public.plasmids p
),
fx AS (
  SELECT
    jf.plasmid_id,
    COALESCE(string_agg(DISTINCT fl.fluor_code, ','), '') AS fluors,
    COALESCE(string_agg(DISTINCT NULLIF(tg.tag_code,''), ','), '') AS tag_codes,
    COALESCE(
      string_agg(
        DISTINCT (COALESCE(fl.fluor_code,'') || COALESCE(':'||NULLIF(tg.tag_code,''),'')),
        ',' ORDER BY (COALESCE(fl.fluor_code,'') || COALESCE(':'||NULLIF(tg.tag_code,''),''))
      ),
      ''
    ) AS fusions,
    COUNT(DISTINCT jpf.fusion_id) AS n_fusions
  FROM jf
  LEFT JOIN public.join_plasmid_fusions jpf ON jpf.plasmid_id = jf.plasmid_id
  LEFT JOIN public.fusions f   ON f.id  = jpf.fusion_id
  LEFT JOIN public.fluors  fl  ON fl.id = f.fluor_id
  LEFT JOIN public.tags    tg  ON tg.id = f.tag_id
  GROUP BY jf.plasmid_id
)
SELECT
  jf.code,
  jf.name,
  jf.nickname,
  jf.resistance,
  jf.supports_invitro_rna,
  COALESCE(fx.fluors,'')      AS fluors,
  COALESCE(fx.tag_codes,'')   AS tag_codes,
  COALESCE(fx.fusions,'')     AS fusions,
  COALESCE(fx.n_fusions,0)    AS n_fusions,
  jf.created_at
FROM jf
LEFT JOIN fx ON fx.plasmid_id = jf.plasmid_id;

COMMIT;
