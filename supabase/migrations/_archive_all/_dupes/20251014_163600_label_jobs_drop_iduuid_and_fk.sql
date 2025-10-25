ALTER TABLE ONLY public.label_items DROP CONSTRAINT IF EXISTS label_items_job_id_fkey;
ALTER TABLE public.label_jobs DROP COLUMN IF EXISTS id_uuid;
ALTER TABLE ONLY public.label_items
  ADD CONSTRAINT label_items_job_id_fkey
  FOREIGN KEY (job_id) REFERENCES public.label_jobs(id) ON DELETE CASCADE;
