with gen as (
    select
        cl.id as clutch_id,
        string_agg(distinct tok.token_pretty, ' ; ' order by tok.token_pretty) as pretty_union
    from public.clutches AS cl
    inner join public.cross_instances AS ci on cl.cross_instance_id = ci.id
    inner join public.crosses AS x on ci.cross_id = x.id
    left join public.v_fish_overview_all AS vm on x.mother_code = vm.fish_code
    left join public.v_fish_overview_all AS vd on x.father_code = vd.fish_code
    left join lateral (
        select coalesce(vm.allele_pretty_name, vm.transgene_pretty_name) as token_pretty
        where coalesce(vm.allele_pretty_name, vm.transgene_pretty_name) is not null
        union all
        select coalesce(vd.allele_pretty_name, vd.transgene_pretty_name)
        where coalesce(vd.allele_pretty_name, vd.transgene_pretty_name) is not null
    ) as tok on true
    group by cl.id
)

update public.clutches cl
set
    clutch_name = coalesce(nullif(btrim(clutch_name), ''), gen.pretty_union),
    clutch_nickname
    = coalesce(nullif(btrim(clutch_nickname), ''), coalesce(nullif(btrim(clutch_name), ''), gen.pretty_union))
from gen  where
    gen.clutch_id = cl.id
    and (
        clutch_name is null or btrim(clutch_name) = ''
        or clutch_nickname is null or btrim(clutch_nickname) = ''
    );
