create or replace view public.v_clutch_treatments_summary as
with base as (
    select
        clutch_id,
        material_type,
        material_code,
        coalesce(nullif(btrim(material_name), ''), material_code) as material_name,
        jsonb_build_object(
            'type', material_type, 'code', material_code, 'name', coalesce(nullif(btrim(material_name), ''), material_code)
        ) as obj
    from public.clutch_plan_treatments
)

select
    clutch_id,
    count(*)::int as treatments_count,
    -- Pretty = codes only
    string_agg(distinct material_code, ' ; ' order by material_code) as treatments_pretty,
    -- If you ever want canonical-with-type as well, uncomment the next line:
    -- string_agg(distinct (material_type || ':' || material_code), ' ; ' order by (material_type || ':' || material_code)) as treatments_canonical,
    jsonb_agg(distinct obj order by obj) as treatments_json
from base  group by clutch_id;
