BEGIN;
DROP VIEW IF EXISTS public.v_fish_overview        CASCADE;
DROP VIEW IF EXISTS public.v_plasmids_overview    CASCADE;
DROP VIEW IF EXISTS public.v_fluors_overview      CASCADE;
DROP VIEW IF EXISTS public.v_transgenes_overview  CASCADE;
DROP VIEW IF EXISTS public.v_clutches_overview    CASCADE;

CREATE VIEW public.v_fish_overview AS
WITH jt AS (
  SELECT f.fish_code,jfta.transgene_base_code,jfta.allele_number,ta.allele_name,ta.allele_nickname,
         COALESCE(NULLIF(ta.allele_nickname,''), ta.allele_name) AS allele_label
  FROM public.join_fish_transgene_alleles jfta
  JOIN public.fish f ON f.id=jfta.fish_id
  LEFT JOIN public.transgene_alleles ta
    ON ta.transgene_base_code=jfta.transgene_base_code AND ta.allele_number=jfta.allele_number
),
mk AS (
  SELECT fish_code,
         string_agg(DISTINCT CASE WHEN COALESCE(allele_label,'')<>'' THEN transgene_base_code||'('||allele_label||')' ELSE transgene_base_code END,
                    ',' ORDER BY CASE WHEN COALESCE(allele_label,'')<>'' THEN transgene_base_code||'('||allele_label||')' ELSE transgene_base_code END) AS markers
  FROM jt GROUP BY fish_code
),
gp AS (
  SELECT fish_code,
         string_agg(DISTINCT (transgene_base_code||'('||allele_label||')'), ', ' ORDER BY (transgene_base_code||'('||allele_label||')')) AS genotype_pretty
  FROM jt WHERE COALESCE(allele_label,'')<>'' GROUP BY fish_code
),
fu AS (
  SELECT jt.fish_code,
         COALESCE(string_agg(DISTINCT fl.fluor_code, ','),'') AS fluors,
         COALESCE(string_agg(DISTINCT NULLIF(tg.tag_code,''), ','),'') AS tags,
         COALESCE(string_agg(DISTINCT (COALESCE(fl.fluor_code,'')||COALESCE(':'||NULLIF(tg.tag_code,''),'')), ','
                              ORDER BY (COALESCE(fl.fluor_code,'')||COALESCE(':'||NULLIF(tg.tag_code,''),''))),'') AS fusions,
         COUNT(DISTINCT pf.id) AS n_fusions
  FROM jt
  JOIN public.plasmids p               ON p.code=jt.transgene_base_code
  JOIN public.join_plasmid_fusions jpf ON jpf.plasmid_id=p.id
  JOIN public.fusions pf               ON pf.id=jpf.fusion_id
  LEFT JOIN public.fluors fl           ON fl.id=pf.fluor_id
  LEFT JOIN public.tags   tg           ON tg.id=pf.tag_id
  GROUP BY jt.fish_code
)
SELECT
  CASE WHEN f.fish_code ~ '^FSH-[A-Z0-9]{8}$' THEN f.fish_code
       WHEN f.fish_code ~ '^\d+$' THEN 'FSH-'||lpad(f.fish_code,8,'0')
       ELSE f.fish_code END AS fish_code_display,
  f.fish_code AS fish_code_raw,
  COALESCE(f.nickname,'') AS nickname,
  f.birthday AS birthday,
  COALESCE(f.genetic_background,'') AS genetic_background,
  COALESCE(f.in_breeding_stage,'') AS line_building_stage,
  COALESCE(gp.genotype_pretty,'') AS genotype_pretty,
  COALESCE(mk.markers,'') AS markers,
  COALESCE(fu.fluors,'') AS fluors,
  COALESCE(fu.tags,'') AS tags,
  COALESCE(fu.fusions,'') AS fusions,
  COALESCE(fu.n_fusions,0) AS n_fusions,
  ''::text AS dyes,
  f.created_at
FROM public.fish f
LEFT JOIN gp ON gp.fish_code=f.fish_code
LEFT JOIN mk ON mk.fish_code=f.fish_code
LEFT JOIN fu ON fu.fish_code=f.fish_code;

CREATE VIEW public.v_plasmids_overview AS
WITH base AS (
  SELECT p.id AS plasmid_id,p.code,p.name,COALESCE(p.nickname,'') AS nickname,COALESCE(p.resistance,'') AS resistance,p.created_at
  FROM public.plasmids p
),
fx AS (
  SELECT b.plasmid_id,
         COALESCE(string_agg(DISTINCT fl.fluor_code, ','),'') AS fluors,
         COALESCE(string_agg(DISTINCT NULLIF(tg.tag_code,''), ','),'') AS tag_codes,
         COALESCE(string_agg(DISTINCT (COALESCE(fl.fluor_code,'')||COALESCE(':'||NULLIF(tg.tag_code,''),'')), ','
                              ORDER BY (COALESCE(fl.fluor_code,'')||COALESCE(':'||NULLIF(tg.tag_code,''),''))),'') AS fusions,
         COUNT(DISTINCT jpf.fusion_id) AS n_fusions
  FROM base b
  LEFT JOIN public.join_plasmid_fusions jpf ON jpf.plasmid_id=b.plasmid_id
  LEFT JOIN public.fusions f  ON f.id=jpf.fusion_id
  LEFT JOIN public.fluors fl  ON fl.id=f.fluor_id
  LEFT JOIN public.tags   tg  ON tg.id=f.tag_id
  GROUP BY b.plasmid_id
)
SELECT b.code,b.name,b.nickname,b.resistance,
       COALESCE(fx.fluors,'') AS fluors,
       COALESCE(fx.tag_codes,'') AS tag_codes,
       COALESCE(fx.fusions,'') AS fusions,
       COALESCE(fx.n_fusions,0) AS n_fusions,
       b.created_at
FROM base b
LEFT JOIN fx ON fx.plasmid_id=b.plasmid_id;

CREATE VIEW public.v_fluors_overview AS
WITH u AS (
  SELECT fl.id,fl.fluor_code,fl.excitation_nm,fl.emission_nm,COALESCE(fl.notes,'') AS notes,fl.created_at
  FROM public.fluors fl
),
cnt AS (
  SELECT u.id,COUNT(DISTINCT f.id) AS n_fusions,COUNT(DISTINCT jpf.plasmid_id) AS n_plasmids
  FROM u
  LEFT JOIN public.fusions f ON f.fluor_id=u.id
  LEFT JOIN public.join_plasmid_fusions jpf ON jpf.fusion_id=f.id
  GROUP BY u.id
)
SELECT u.fluor_code,u.fluor_code AS name,u.excitation_nm,u.emission_nm,u.notes,
       COALESCE(cnt.n_fusions,0) AS n_fusions,COALESCE(cnt.n_plasmids,0) AS n_plasmids,u.created_at
FROM u LEFT JOIN cnt ON cnt.id=u.id;

CREATE VIEW public.v_transgenes_overview AS
WITH al AS (
  SELECT ta.transgene_base_code,ta.allele_number,ta.allele_name,ta.allele_nickname,
         COALESCE(NULLIF(ta.allele_nickname,''), ta.allele_name) AS allele_label
  FROM public.transgene_alleles ta
),
agg AS (
  SELECT al.transgene_base_code,COUNT(*) AS n_alleles,
         string_agg(DISTINCT (al.transgene_base_code||'('||al.allele_label||')'), ', '
                    ORDER BY (al.transgene_base_code||'('||al.allele_label||')')) AS alleles_pretty
  FROM al GROUP BY al.transgene_base_code
),
nfish AS (
  SELECT jfta.transgene_base_code,COUNT(DISTINCT jfta.fish_id) AS n_fish
  FROM public.join_fish_transgene_alleles jfta GROUP BY jfta.transgene_base_code
)
SELECT tg.transgene_base_code,
       COALESCE(agg.n_alleles,0) AS n_alleles,
       COALESCE(nfish.n_fish,0)  AS n_fish,
       COALESCE(agg.alleles_pretty,'') AS alleles_pretty
FROM public.transgenes tg
LEFT JOIN agg   ON agg.transgene_base_code=tg.transgene_base_code
LEFT JOIN nfish ON nfish.transgene_base_code=tg.transgene_base_code;

CREATE VIEW public.v_clutches_overview AS
WITH base AS (
  SELECT ci.id AS clutch_instance_id,
         ci.clutch_instance_code AS clutch_code,
         ci.created_at AS clutch_created_at,
         cr.id AS cross_id,
         cr.tank_pair_id AS tank_pair_id,
         cr.tank_pair_id::text AS tank_pair_code,
         cr.cross_run_code AS cross_run_code,
         COALESCE(cr.created_at::date, ci.created_at::date) AS cross_date
  FROM public.clutch_instances ci
  LEFT JOIN public.crosses cr ON cr.id=ci.cross_instance_id
),
tc AS (
  SELECT b.clutch_instance_id,tc.id AS treated_clutch_id,tc.treated_clutch_code
  FROM base b
  LEFT JOIN public.treated_clutches tc ON tc.clutch_instance_id=b.clutch_instance_id
),
tx AS (
  SELECT tc.clutch_instance_id,
         COALESCE(string_agg(DISTINCT COALESCE(
           NULLIF((to_jsonb(t)->>'name')::text,''),
           NULLIF((to_jsonb(t)->>'code')::text,''),
           NULLIF((to_jsonb(t)->>'treatment_code')::text,''),
           NULLIF((to_jsonb(t)->>'label')::text,''),
           t.id::text
         ), ',' ORDER BY COALESCE(
           NULLIF((to_jsonb(t)->>'name')::text,''),
           NULLIF((to_jsonb(t)->>'code')::text,''),
           NULLIF((to_jsonb(t)->>'treatment_code')::text,''),
           NULLIF((to_jsonb(t)->>'label')::text,''),
           t.id::text
         )), '') AS treatments,
         COUNT(DISTINCT t.id) AS n_treatments
  FROM tc
  LEFT JOIN public.join_clutch_treatments jct ON jct.treated_clutch_id=tc.treated_clutch_id
  LEFT JOIN public.treatments t ON t.id=jct.treatment_id
  GROUP BY tc.clutch_instance_id
)
SELECT b.clutch_code,b.clutch_instance_id,b.clutch_created_at,b.tank_pair_id,b.tank_pair_code,
       b.cross_run_code,b.cross_date,
       COALESCE(tx.treatments,'') AS treatments,
       COALESCE(tx.n_treatments,0) AS n_treatments
FROM base b
LEFT JOIN tx ON tx.clutch_instance_id=b.clutch_instance_id;
COMMIT;
