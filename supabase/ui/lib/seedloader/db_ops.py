from typing import Dict, List, Optional

from sqlalchemy import text

from lib.db import exec_sql  # you already have this
from .utils import blank, none_if_blank, parse_date


def ensure_tank_helpers(cx):
    exec_sql(cx, "create sequence if not exists public.tank_label_seq")
    exec_sql(
        cx,
        """
    create or replace function public.next_tank_code(prefix text)
    returns text language plpgsql as $func$
    declare n bigint;
    begin
      n := nextval('public.tank_label_seq');
      return prefix || to_char(n, 'FM000');
    end
    $func$;
    """,
    )


def ensure_auto_fish_helpers(cx):
    exec_sql(cx, "create sequence if not exists public.auto_fish_seq")
    exec_sql(
        cx,
        """
    create or replace function public.next_auto_fish_code()
    returns text language sql as $$
      select
        'FSH-' || to_char(now(), 'YYYY') || '-' ||
        to_char(nextval('public.auto_fish_seq'), 'FM000')
    $$;
    """,
    )


def upsert_transgenes(cx, df_tg):
    exec_sql(cx, "alter table public.transgenes add column if not exists name text")
    exec_sql(
        cx, "alter table public.transgenes add column if not exists description text"
    )
    upsert = text(
        """
    insert into public.transgenes(transgene_base_code, name, description)
    values (:tbc, :name, :desc)
    on conflict (transgene_base_code) do update
      set name = coalesce(nullif(excluded.name, ''), public.transgenes.name),
          description = coalesce(nullif(excluded.description, ''), public.transgenes.description)
    """
    )
    for r in df_tg.to_dict(orient="records"):
        cx.execute(
            upsert,
            {
                "tbc": blank(r.get("transgene_base_code")),
                "name": blank(r.get("name")),
                "desc": blank(r.get("description")),
            },
        )


def upsert_alleles(cx, df_ac):
    # Table name aligned to your FK: public.transgene_alleles
    exec_sql(
        cx,
        """
        create table if not exists public.transgene_alleles(
          transgene_base_code text not null,
          allele_number text not null,
          allele_name text,
          description text,
          primary key (transgene_base_code, allele_number)
        )
    """,
    )
    upsert = text(
        """
        insert into public.transgene_alleles(transgene_base_code, allele_number, allele_name, description)
        values (:tbc, :alle, :aname, :desc)
        on conflict (transgene_base_code, allele_number) do update
          set allele_name = coalesce(nullif(excluded.allele_name,''), public.transgene_alleles.allele_name),
              description = coalesce(nullif(excluded.description,''), public.transgene_alleles.description)
    """
    )
    for r in df_ac.to_dict(orient="records"):
        cx.execute(
            upsert,
            {
                "tbc": blank(r.get("transgene_base_code")),
                "alle": blank(r.get("allele_number")),
                "aname": blank(r.get("allele_name")),
                "desc": blank(r.get("description")),
            },
        )


def ensure_transgenes_exist(cx, base_codes: List[str]):
    exec_sql(cx, "alter table public.transgenes add column if not exists name text")
    upsert_t = text(
        """
        insert into public.transgenes(transgene_base_code, name)
        values (:tbc, :tbc)
        on conflict (transgene_base_code) do nothing
    """
    )
    for tbc in base_codes:
        cx.execute(upsert_t, {"tbc": blank(tbc)})


def insert_fish(cx, df_fish, default_batch: Optional[str]):
    # Required: name
    cols = [
        "name",
        "batch_label",
        "line_building_stage",
        "nickname",
        "date_of_birth",
        "description",
        "strain",
    ]
    for c in cols:
        if c not in df_fish.columns:
            df_fish[c] = None

    if default_batch:
        df_fish["batch_label"] = df_fish["batch_label"].apply(
            lambda v: default_batch if (blank(v) == "") else v
        )
    df_fish["date_of_birth"] = df_fish["date_of_birth"].apply(parse_date)

    exec_sql(cx, "alter table public.fish add column if not exists batch_label text")
    exec_sql(
        cx,
        "alter table public.fish add column if not exists line_building_stage text",
    )
    exec_sql(cx, "alter table public.fish add column if not exists nickname text")
    exec_sql(cx, "alter table public.fish add column if not exists description text")
    exec_sql(cx, "alter table public.fish add column if not exists strain text")
    exec_sql(cx, "alter table public.fish add column if not exists date_of_birth date")
    exec_sql(cx, "alter table public.fish add column if not exists auto_fish_code text")

    ins = text(
        """
        insert into public.fish(
            name, fish_code, batch_label, line_building_stage, nickname, date_of_birth, description, strain, auto_fish_code
        )
        select :name, NULL, :batch_label, :line_building_stage, :nickname, :date_of_birth, :description, :strain,
               public.next_auto_fish_code()
        where not exists (select 1 from public.fish f where f.name = :name)
    """
    )

    for r in df_fish[cols].to_dict(orient="records"):
        cx.execute(
            ins,
            {
                "name": blank(r.get("name")),
                "batch_label": blank(r.get("batch_label")),
                "line_building_stage": blank(r.get("line_building_stage")),
                "nickname": blank(r.get("nickname")),
                "date_of_birth": none_if_blank(r.get("date_of_birth")),
                "description": blank(r.get("description")),
                "strain": blank(r.get("strain")),
            },
        )


def insert_links_by_name(cx, df_links):
    sql = """
        insert into public.fish_transgene_alleles(fish_id, transgene_base_code, allele_number, zygosity)
        select f.id, :tbc, nullif(:alle,''), nullif(:zyg,'')
        from public.fish f
        where f.name = :fname
        on conflict do nothing
    """
    ins = text(sql)
    for r in df_links.to_dict(orient="records"):
        cx.execute(
            ins,
            {
                "fname": blank(r.get("fish_name")),
                "tbc": blank(r.get("transgene_base_code")),
                "alle": blank(r.get("allele_number")),
                "zyg": blank(r.get("zygosity")),
            },
        )


def assign_missing_tanks(cx):
    ensure_tank_helpers(cx)
    exec_sql(
        cx,
        """
        insert into public.tank_assignments(fish_id, tank_label, status)
        select f.id, public.next_tank_code('TANK-'), 'inactive'
        from public.fish f
        left join public.tank_assignments ta on ta.fish_id = f.id
        where ta.fish_id is null
        """,
    )