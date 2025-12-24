-- ROI-channel QC (keep/kill at per-channel granularity)
create table if not exists public.imaging_roi_channel_qc (
  id uuid primary key default gen_random_uuid(),

  roi_code text not null,
  cam text null,
  channel text null,
  wavelength_nm int null,

  keep boolean not null default true,
  kill_reason text null,

  source text null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Uniqueness: one QC row per ROI+channel tuple
create unique index if not exists imaging_roi_channel_qc_uniq
  on public.imaging_roi_channel_qc (roi_code, cam, channel, wavelength_nm);

-- Minimal FK (only if roi_code is guaranteed unique in your ROI table)
-- If roi_code is not unique, we should FK to roi_id instead; we can tighten later.
-- alter table public.imaging_roi_channel_qc
--   add constraint imaging_roi_channel_qc_roi_code_fk
--   foreign key (roi_code) references public.imaging_roi_annotations (roi_code);

-- Auto-update timestamp
create or replace function public._touch_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists trg_touch_roi_channel_qc on public.imaging_roi_channel_qc;
create trigger trg_touch_roi_channel_qc
before update on public.imaging_roi_channel_qc
for each row execute function public._touch_updated_at();

-- Rollup view for UI joins
create or replace view public.v_roi_channel_qc_star as
select
  roi_code,
  bool_or(not keep) as has_killed_channels,
  count(*) as n_channels_total,
  sum(case when keep then 1 else 0 end) as n_channels_kept,
  string_agg(
    distinct
    concat_ws(':', cam, channel, case when wavelength_nm is null then null else wavelength_nm::text end),
    '; ' order by concat_ws(':', cam, channel, case when wavelength_nm is null then null else wavelength_nm::text end)
  ) filter (where keep) as kept_channels_key
from public.imaging_roi_channel_qc
group by roi_code;
