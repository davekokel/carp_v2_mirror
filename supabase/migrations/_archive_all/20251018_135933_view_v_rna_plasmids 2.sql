create or replace view public.v_rna_plasmids as
with p as (
    select
        p.id as plasmid_id,
        p.name,
        p.nickname,
        p.created_at,
        p.created_by, 'RNA-' || p.code
    from public.plasmids AS p
    where p.supports_invitro_rna = true
),

pr as (
    select
        rr.rna_code as code,
        null::uuid as plasmid_id,
        rr.rna_nickname as registry_nickname,
        rr.created_at as registry_created_at,
        rr.created_by as registry_created_by
    from public.rna_registry AS rr
)

select
    coalesce(p.plasmid_id, pr.plasmid_id) as plasmid_id,
    coalesce(p.code, pr.code) as code,
    coalesce(p.name, pr.code) as name,
    coalesce(pr.registry_nickname, p.nickname, '') as nickname,
    coalesce(p.created_at, pr.registry_created_at) as created_at,
    coalesce(p.created_by, pr.registry_created_by) as created_by,
    case when p.plasmid_id is not null then 'plasmids' else 'rna_registry' end as source
from p  full outer join pr AS on p.code = pr.code;
