begin;

with ranked as (
  select
    transgene_base_code,
    allele_number,
    allele_name,
    allele_nickname,
    row_number() over (
      partition by transgene_base_code, btrim(coalesce(allele_nickname,''))
      order by allele_number
    ) as rn
  from public.transgene_alleles
  where allele_nickname is not null and length(btrim(allele_nickname))>0
),
dupes as (
  select * from ranked where rn > 1
)
update public.transgene_alleles t
set allele_nickname = t.allele_name
from dupes d
where t.transgene_base_code = d.transgene_base_code
  and t.allele_number       = d.allele_number;

commit;
