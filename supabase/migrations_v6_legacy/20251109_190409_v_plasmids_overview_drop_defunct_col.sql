BEGIN;

CREATE OR REPLACE VIEW public.v_plasmids_overview AS
WITH base AS (
  SELECT
    p.id                      AS plasmid_id,
    p.code,
    p.name,
    COALESCE(p.nickname,'')   AS nickname,
    COALESCE(p.resistance,'') AS resistance,
    p.created_at
  FROM public.plasmids p
),
fx AS (
  SELECT
    b.plasmid_id,
    COALESCE(string_agg(DISTINCT fl.fluor_code, ','), '')          AS fluors,
    COALESCE(string_agg(DISTINCT NULLIF(tg.tag_code,''), ','), '') AS tag_codes,
    COALESCE(
      string_agg(
        DISTINCT (COALESCE(fl.fluor_code,'') || COALESCE(':'||NULLIF(tg.tag_code,''),'')),
        ',' ORDER BY (COALESCE(fl.fluor_code,'') || COALESCE(':'||NULLIF(tg.tag_code,''),''))
      ),
      ''
    ) AS fusions,
    COUNT(DISTINCT jpf.fusion_id) AS n_fusions
  FROM base b
  LEFT JOIN public.join_plasmid_fusions jpf ON jpf.plasmid_id = b.plasmid_id
  LEFT JOIN public.fusions f   ON f.id  = jpf.fusion_id
  LEFT JOIN public.fluors  fl  ON fl.id = f.fluor_id
  LEFT JOIN public.tags    tg  ON tg.id = f.tag_id
  GROUP BY b.plasmid_id
)
SELECT
  b.code,
  b.name,
  b.nickname,
  b.resistance,
  COALESCE(fx.fluors,'')    AS fluors,
  COALESCE(fx.tag_codes,'') AS tag_codes,
  COALESCE(fx.fusions,'')   AS fusions,
  COALESCE(fx.n_fusions,0)  AS n_fusions,
  b.created_at
FROM base b
LEFT JOIN fx ON fx.plasmid_id = b.plasmid_id;

COMMIT;
