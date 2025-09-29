from sqlalchemy import text


def sql_batches():
    return """
    SELECT DISTINCT COALESCE(NULLIF(batch_label,''),'(none)') AS batch
    FROM public.fish
    ORDER BY 1
    """


def detect_tank_select_join(cx):
    # returns tuple (select_clause, join_clause)
    tbl_exists = text(
        """
        SELECT EXISTS (
          SELECT 1 FROM information_schema.tables
          WHERE table_schema='public' AND table_name=:t
        );
    """
    )
    col_exists = text(
        """
        SELECT EXISTS (
          SELECT 1 FROM information_schema.columns
          WHERE table_schema='public' AND table_name=:tbl AND column_name=:col
        );
    """
    )

    # fish columns
    if cx.execute(col_exists, {"tbl": "fish", "col": "tank"}).scalar():
        return "f.tank AS tank, NULL::text AS status", ""
    if cx.execute(col_exists, {"tbl": "fish", "col": "tank_label"}).scalar():
        return "f.tank_label AS tank, NULL::text AS status", ""

    # tank_assignments preferred (has status)
    if cx.execute(tbl_exists, {"t": "tank_assignments"}).scalar():
        return (
            "ta.tank_label AS tank, ta.status::text AS status",
            "LEFT JOIN public.tank_assignments ta ON ta.fish_id = f.id",
        )

    # fish_tanks + tanks (no status)
    has_ft = cx.execute(tbl_exists, {"t": "fish_tanks"}).scalar()
    has_t = cx.execute(tbl_exists, {"t": "tanks"}).scalar()
    if has_ft and has_t:
        lab_name = cx.execute(col_exists, {"tbl": "tanks", "col": "name"}).scalar()
        lab_label = cx.execute(col_exists, {"tbl": "tanks", "col": "label"}).scalar()
        tank_expr = "t.name" if lab_name else ("t.label" if lab_label else "NULL")
        type_q = text(
            """
            SELECT data_type
            FROM information_schema.columns
            WHERE table_schema='public' AND table_name=:tbl AND column_name=:col
        """
        )
        ft_tid = cx.execute(type_q, {"tbl": "fish_tanks", "col": "tank_id"}).scalar()
        t_id = cx.execute(type_q, {"tbl": "tanks", "col": "id"}).scalar()
        join_expr = (
            "t.id = ft.tank_id" if (ft_tid == t_id) else "t.id::text = ft.tank_id::text"
        )
        return (
            f"COALESCE({tank_expr}, '') AS tank, NULL::text AS status",
            f"LEFT JOIN public.fish_tanks ft ON ft.fish_id = f.id LEFT JOIN public.tanks t ON {join_expr}",
        )

    return "'' AS tank, NULL::text AS status", ""


def sql_overview(tank_select: str, tank_join: str, where_sql: str = "") -> str:
    return f"""
    WITH tg AS (
      SELECT
        ft.fish_id,
        string_agg(DISTINCT t.transgene_base_code, ', ' ORDER BY t.transgene_base_code) AS transgenes
      FROM public.fish_transgenes ft
      JOIN public.transgenes t
        ON t.transgene_base_code = ft.transgene_code
      GROUP BY ft.fish_id
    ),
    alle AS (
      SELECT
        x.fish_id,
        string_agg(DISTINCT x.allele_label, ', ' ORDER BY x.allele_label) AS alleles
      FROM (
        SELECT
          f.id AS fish_id,
          trim(CONCAT(
            fta.transgene_base_code,
            CASE WHEN NULLIF(fta.allele_number,'') IS NOT NULL
                 THEN '('||fta.allele_number||')' ELSE '' END
          )) AS allele_label
        FROM public.fish f
        LEFT JOIN public.fish_transgene_alleles fta ON fta.fish_id = f.id
      ) x
      GROUP BY x.fish_id
    )
    SELECT
      f.id,
      f.name                       AS fish_name,
      f.auto_fish_code             AS auto_fish_code,
      f.batch_label                AS batch,
      f.line_building_stage        AS line_building_stage,
      f.nickname,
      f.date_of_birth,
      {tank_select},
      COALESCE(tg.transgenes, '')  AS transgenes,
      COALESCE(alle.alleles, '')   AS alleles,
      f.description
    FROM public.fish f
    LEFT JOIN tg   ON tg.fish_id   = f.id
    LEFT JOIN alle ON alle.fish_id = f.id
    {tank_join}
    {where_sql}
    ORDER BY fish_name
    LIMIT :lim
    """


def sql_auto_assign():
    return """
    WITH candidates AS (
      SELECT
        f.id AS fish_id,
        CASE
          WHEN CURRENT_DATE - COALESCE(f.date_of_birth::date, CURRENT_DATE) < 30
            THEN 'NURSERY-'
          ELSE 'TANK-'
        END AS prefix
      FROM public.fish f
      LEFT JOIN public.tank_assignments ta ON ta.fish_id = f.id
      WHERE ta.fish_id IS NULL
        AND COALESCE(NULLIF(f.batch_label,''),'(none)') = :batch
    )
    INSERT INTO public.tank_assignments(fish_id, tank_label, status)
    SELECT fish_id, public.next_tank_code(prefix), 'inactive'::tank_status
    FROM candidates
    ON CONFLICT (fish_id) DO UPDATE
    SET tank_label = EXCLUDED.tank_label,
        status     = 'inactive';
    """
