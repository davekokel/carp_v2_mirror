--
-- PostgreSQL database dump
--


-- Dumped from database version 16.10 (Homebrew)
-- Dumped by pg_dump version 18.0

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
-- SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: v_containers_candidates; Type: VIEW; Schema: public; Owner: postgres
--

CREATE OR REPLACE VIEW public.v_containers_candidates AS
SELECT
    id_uuid,
    container_type,
    label,
    status,
    created_by,
    created_at,
    status_changed_at,
    activated_at,
    deactivated_at,
    last_seen_at,
    note
FROM public.containers
WHERE
    (container_type = ANY(ARRAY['inventory_tank'::text, 'crossing_tank'::text, 'holding_tank'::text, 'nursery_tank'::text, 'petri_dish'::text]));


ALTER VIEW public.v_containers_candidates OWNER TO postgres;

--
-- Name: v_cross_plan_runs_enriched; Type: VIEW; Schema: public; Owner: postgres
--

CREATE OR REPLACE VIEW public.v_cross_plan_runs_enriched AS
SELECT
    r.id,
    r.plan_id,
    r.seq,
    r.planned_date,
    r.status,
    r.note,
    r.created_by,
    r.created_at,
    p.plan_title,
    p.plan_nickname,
    p.mother_fish_id,
    p.father_fish_id,
    fm.fish_code AS mother_fish_code,
    ff.fish_code AS father_fish_code,
    ca.label AS tank_a_label,
    cb.label AS tank_b_label
FROM (((((
    public.cross_plan_runs r
    INNER JOIN public.cross_plans AS p ON ((r.plan_id = p.id))
)
LEFT JOIN public.fish AS fm ON ((p.mother_fish_id = fm.id))
)
LEFT JOIN public.fish AS ff ON ((p.father_fish_id = ff.id))
)
LEFT JOIN public.containers AS ca ON ((r.tank_a_id = ca.id_uuid))
)
LEFT JOIN public.containers AS cb ON ((r.tank_b_id = cb.id_uuid))
);


ALTER VIEW public.v_cross_plan_runs_enriched OWNER TO postgres;

--
-- Name: v_cross_plans_enriched; Type: VIEW; Schema: public; Owner: postgres
--

CREATE OR REPLACE VIEW public.v_cross_plans_enriched AS
SELECT
    p.id,
    p.plan_date,
    p.status,
    p.created_by,
    p.note,
    p.created_at,
    p.mother_fish_id,
    fm.fish_code AS mother_fish_code,
    p.father_fish_id,
    ff.fish_code AS father_fish_code,
    p.tank_a_id,
    ca.label AS tank_a_label,
    p.tank_b_id,
    cb.label AS tank_b_label,
    COALESCE((
        SELECT
            STRING_AGG(
                FORMAT(
                    '%s[%s]%s'::text,
                    g.transgene_base_code,
                    g.allele_number,
                    COALESCE((' '::text || g.zygosity_planned), ''::text)
                ),
                ', '::text ORDER BY g.transgene_base_code, g.allele_number
            ) AS string_agg
        FROM public.cross_plan_genotype_alleles AS g
        WHERE (g.plan_id = p.id)
    ), ''::text) AS genotype_plan,
    COALESCE((SELECT
        STRING_AGG(TRIM(BOTH ' '::text FROM CONCAT(
            t.treatment_name,
            CASE
                WHEN (t.amount IS NOT null) THEN (' '::text || (t.amount)::text)
                ELSE ''::text
            END,
            CASE
                WHEN (t.units IS NOT null) THEN (' '::text || t.units)
                ELSE ''::text
            END,
            CASE
                WHEN (t.timing_note IS NOT null) THEN ((' ['::text || t.timing_note) || ']'::text)
                ELSE ''::text
            END
        )), ', '::text ORDER BY t.treatment_name) AS string_agg
    FROM public.cross_plan_treatments AS t
    WHERE (t.plan_id = p.id)), ''::text) AS treatments_plan
FROM ((((
    public.cross_plans p
    LEFT JOIN public.fish AS fm ON ((p.mother_fish_id = fm.id))
)
LEFT JOIN public.fish AS ff ON ((p.father_fish_id = ff.id))
)
LEFT JOIN public.containers AS ca ON ((p.tank_a_id = ca.id_uuid))
)
LEFT JOIN public.containers AS cb ON ((p.tank_b_id = cb.id_uuid))
);


ALTER VIEW public.v_cross_plans_enriched OWNER TO postgres;

--
-- Name: v_crosses_status; Type: VIEW; Schema: public; Owner: postgres
--

CREATE OR REPLACE VIEW public.v_crosses_status AS
SELECT
    id_uuid,
    mother_code,
    father_code,
    planned_for,
    created_by,
    created_at,
    CASE
        WHEN (EXISTS (
            SELECT 1
            FROM public.clutches AS x
            WHERE (x.cross_id = c.id_uuid)
        )) THEN 'realized'::text
        ELSE 'planned'::text
    END AS status
FROM public.crosses AS c;


ALTER VIEW public.v_crosses_status OWNER TO postgres;

--
-- Name: v_clutches_concept_overview; Type: VIEW; Schema: public; Owner: postgres
--

CREATE OR REPLACE VIEW public.v_clutches_concept_overview AS
WITH base AS (
    SELECT
        cp.id_uuid AS clutch_plan_id,
        pc.id_uuid AS planned_cross_id,
        cp.clutch_code,
        cp.planned_name AS clutch_name,
        cp.planned_nickname AS clutch_nickname,
        pc.cross_date AS date_planned,
        cp.created_by,
        cp.created_at,
        COALESCE(cp.note, pc.note) AS note
    FROM (
        public.clutch_plans AS cp
        LEFT JOIN public.planned_crosses AS pc ON ((cp.id_uuid = pc.clutch_id))
    )
),

inst AS (
    SELECT
        c.planned_cross_id,
        (COUNT(*))::integer AS n_instances,
        (COUNT(c.cross_id))::integer AS n_crosses,
        MAX(c.date_birth) AS latest_date_birth
    FROM public.clutches AS c
    GROUP BY c.planned_cross_id
),

cont AS (
    SELECT
        c.planned_cross_id,
        (COUNT(cc.*))::integer AS n_containers
    FROM (
        public.clutches AS c
        INNER JOIN public.clutch_containers AS cc ON ((c.id_uuid = cc.clutch_id))
    )
    GROUP BY c.planned_cross_id
)

SELECT
    b.clutch_plan_id,
    b.planned_cross_id,
    b.clutch_code,
    b.clutch_name,
    b.clutch_nickname,
    b.date_planned,
    b.created_by,
    b.created_at,
    b.note,
    i.latest_date_birth,
    COALESCE(i.n_instances, 0) AS n_instances,
    COALESCE(COALESCE(i.n_crosses, 0), 0) AS n_crosses,
    COALESCE(ct.n_containers, 0) AS n_containers
FROM ((
    base b
    LEFT JOIN inst AS i ON ((b.planned_cross_id = i.planned_cross_id))
)
LEFT JOIN cont AS ct ON ((b.planned_cross_id = ct.planned_cross_id))
)
ORDER BY
    COALESCE(((b.date_planned)::timestamp without time zone)::timestamp with time zone, b.created_at) DESC NULLS LAST;


ALTER VIEW public.v_clutches_concept_overview OWNER TO postgres;

--
-- Name: v_clutches_overview_human; Type: VIEW; Schema: public; Owner: postgres
--

CREATE OR REPLACE VIEW public.v_clutches_overview_human AS
WITH base AS (
    SELECT
        c.id_uuid AS clutch_id,
        c.date_birth,
        c.created_by,
        c.created_at,
        c.note,
        c.batch_label,
        c.seed_batch_id,
        c.planned_cross_id,
        cp.clutch_code,
        cp.planned_name AS clutch_name,
        c.cross_id,
        COALESCE(mt.label, mt.tank_code) AS mom_tank_label,
        COALESCE(ft.label, ft.tank_code) AS dad_tank_label
    FROM ((((
        public.clutches c
        LEFT JOIN public.planned_crosses AS pc ON ((c.planned_cross_id = pc.id_uuid))
    )
    LEFT JOIN public.clutch_plans AS cp ON ((pc.clutch_id = cp.id_uuid))
    )
    LEFT JOIN public.containers AS mt ON ((pc.mother_tank_id = mt.id_uuid))
    )
    LEFT JOIN public.containers AS ft ON ((pc.father_tank_id = ft.id_uuid))
    )
),

instances AS (
    SELECT
        cc.clutch_id,
        (COUNT(*))::integer AS n_instances
    FROM public.clutch_containers AS cc
    GROUP BY cc.clutch_id
),

crosses_via_clutches AS (
    SELECT
        b_1.clutch_id,
        (COUNT(x.id_uuid))::integer AS n_crosses
    FROM (
        base AS b_1
        LEFT JOIN public.crosses AS x ON ((b_1.cross_id = x.id_uuid))
    )
    GROUP BY b_1.clutch_id
)

SELECT
    b.clutch_id,
    b.date_birth,
    b.created_by,
    b.created_at,
    b.note,
    b.batch_label,
    b.seed_batch_id,
    b.clutch_code,
    b.clutch_name,
    null::text AS clutch_nickname,
    b.mom_tank_label,
    b.dad_tank_label,
    COALESCE(i.n_instances, 0) AS n_instances,
    COALESCE(cx.n_crosses, 0) AS n_crosses
FROM ((
    base b
    LEFT JOIN instances AS i ON ((b.clutch_id = i.clutch_id))
)
LEFT JOIN crosses_via_clutches AS cx ON ((b.clutch_id = cx.clutch_id))
)
ORDER BY
    COALESCE(((b.date_birth)::timestamp without time zone)::timestamp with time zone, b.created_at) DESC NULLS LAST;


ALTER VIEW public.v_clutches_overview_human OWNER TO postgres;

--
-- Name: v_cross_runs; Type: VIEW; Schema: public; Owner: postgres
--

CREATE OR REPLACE VIEW public.v_cross_runs AS
WITH cl AS (
    SELECT
        clutches.cross_instance_id,
        (COUNT(*))::integer AS n_clutches
    FROM public.clutches
    GROUP BY clutches.cross_instance_id
),

cnt AS (
    SELECT
        c.cross_instance_id,
        (COUNT(cc.*))::integer AS n_containers
    FROM (
        public.clutches AS c
        INNER JOIN public.clutch_containers AS cc ON ((c.id_uuid = cc.clutch_id))
    )
    GROUP BY c.cross_instance_id
)

SELECT
    ci.id_uuid AS cross_instance_id,
    ci.cross_run_code,
    ci.cross_date,
    x.id_uuid AS cross_id,
    x.mother_code AS mom_code,
    x.father_code AS dad_code,
    cm.label AS mother_tank_label,
    cf.label AS father_tank_label,
    ci.note AS run_note,
    ci.created_by AS run_created_by,
    ci.created_at AS run_created_at,
    COALESCE(x.cross_code, (x.id_uuid)::text) AS cross_code,
    COALESCE(cl.n_clutches, 0) AS n_clutches,
    COALESCE(cnt.n_containers, 0) AS n_containers
FROM (((((
    public.cross_instances ci
    INNER JOIN public.crosses AS x ON ((ci.cross_id = x.id_uuid))
)
LEFT JOIN public.containers AS cm ON ((ci.mother_tank_id = cm.id_uuid))
)
LEFT JOIN public.containers AS cf ON ((ci.father_tank_id = cf.id_uuid))
)
LEFT JOIN cl ON ((ci.id_uuid = cl.cross_instance_id)))
LEFT JOIN cnt ON ((ci.id_uuid = cnt.cross_instance_id)))
ORDER BY ci.cross_date DESC, ci.created_at DESC;


ALTER VIEW public.v_cross_runs OWNER TO postgres;

--
-- Name: v_crosses_concept; Type: VIEW; Schema: public; Owner: postgres
--

CREATE OR REPLACE VIEW public.v_crosses_concept AS
WITH runs AS (
    SELECT
        cross_instances.cross_id,
        (COUNT(*))::integer AS n_runs,
        MAX(cross_instances.cross_date) AS latest_cross_date
    FROM public.cross_instances
    GROUP BY cross_instances.cross_id
),

cl AS (
    SELECT
        clutches.cross_id,
        (COUNT(*))::integer AS n_clutches
    FROM public.clutches
    GROUP BY clutches.cross_id
),

cnt AS (
    SELECT
        c.cross_id,
        (COUNT(cc.*))::integer AS n_containers
    FROM (
        public.clutches AS c
        INNER JOIN public.clutch_containers AS cc ON ((c.id_uuid = cc.clutch_id))
    )
    GROUP BY c.cross_id
)

SELECT
    x.id_uuid AS cross_id,
    x.mother_code AS mom_code,
    x.father_code AS dad_code,
    x.created_by,
    x.created_at,
    runs.latest_cross_date,
    COALESCE(x.cross_code, (x.id_uuid)::text) AS cross_code,
    COALESCE(runs.n_runs, 0) AS n_runs,
    COALESCE(cl.n_clutches, 0) AS n_clutches,
    COALESCE(cnt.n_containers, 0) AS n_containers
FROM (((
    public.crosses x
    LEFT JOIN runs ON ((x.id_uuid = runs.cross_id))
)
LEFT JOIN cl ON ((x.id_uuid = cl.cross_id)))
LEFT JOIN cnt ON ((x.id_uuid = cnt.cross_id)))
ORDER BY x.created_at DESC;


ALTER VIEW public.v_crosses_concept OWNER TO postgres;

--
-- Name: v_planned_clutches_overview; Type: VIEW; Schema: public; Owner: postgres
--

CREATE OR REPLACE VIEW public.v_planned_clutches_overview AS
WITH x AS (
    SELECT
        cp.id_uuid AS clutch_plan_id,
        pc.id_uuid AS planned_cross_id,
        cp.clutch_code,
        cp.planned_name AS clutch_name,
        cp.planned_nickname AS clutch_nickname,
        pc.cross_date,
        cp.created_by,
        cp.created_at,
        COALESCE(cp.note, pc.note) AS note
    FROM (
        public.clutch_plans AS cp
        LEFT JOIN public.planned_crosses AS pc ON ((cp.id_uuid = pc.clutch_id))
    )
),

tx AS (
    SELECT
        t.clutch_id AS clutch_plan_id,
        (COUNT(*))::integer AS n_treatments
    FROM public.clutch_plan_treatments AS t
    GROUP BY t.clutch_id
)

SELECT
    x.clutch_plan_id,
    x.planned_cross_id,
    x.clutch_code,
    x.clutch_name,
    x.clutch_nickname,
    x.cross_date,
    x.created_by,
    x.created_at,
    x.note,
    COALESCE(tx.n_treatments, 0) AS n_treatments
FROM (
    x
    LEFT JOIN tx ON ((x.clutch_plan_id = tx.clutch_plan_id))
)
ORDER BY
    COALESCE(((x.cross_date)::timestamp without time zone)::timestamp with time zone, x.created_at) DESC NULLS LAST;


ALTER VIEW public.v_planned_clutches_overview OWNER TO postgres;

--
-- PostgreSQL database dump complete
--
