# ROI rollups logic

## Genotype sources
The canonical genotype display for ROI-level views is:

1. Transgene-derived genotype (preferred)
   - Comes from v_roi_overview.genotype_* fields, ultimately derived from:
     - legacy parent definitions (when present)
     - enriched ROI genotype basecodes (raw.legacy_roi_enriched_v9)
2. Genetic background fallback (when no transgenes)
   - Comes from public.clutches.genetic_background
   - For legacy imaging, this is currently forced to “casper” by loader policy.

## Treatment sources
Treatment tokens come from public.treatments → public.treatment_mixes → public.treatment_mix_constructs
and are rendered as typed tokens like:
  plasmid(mgco-1); rna(pdqm-112)

## Rollup rendering
For treated ROIs, the rollup is:
  <treatment_tokens_typed> > <genotype_display>

This can legitimately produce overlap (a basecode appearing on both sides) if a fish is transgenic for a marker
and was also injected with the same marker, but we treat that as allowed-by-data, not inferred-by-logic.

## Anti-inference policy
We do not infer injections from dataset_slug/experiment naming when an imaging sheet row exists.
Slug-based inference (if used at all) must be restricted to inferred rows / missing imaging rows only.
