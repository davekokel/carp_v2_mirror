--
-- PostgreSQL database dump
--

\restrict qfQRSj2sQojOvgn7B25cW8LTr7tRrbeNTgKVQ8fESwT29HnKlYRtTcX2sHHlwbU

-- Dumped from database version 17.4
-- Dumped by pg_dump version 17.6

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Data for Name: treatments; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.treatments VALUES ('35bb3db3-f097-482d-a3f5-4fb73c2fd6ea', 'injected_plasmid', NULL, '2025-08-11 00:00:00+00', 'dk', 'good fluorescence at 5 dpf', '2025-09-23 22:35:52.342906+00', NULL, NULL, DEFAULT, '71fb0390-12db-480b-9ef7-ede4cdc739ff', 'pTol2-elavl3_GCaMP6s');
INSERT INTO public.treatments VALUES ('b001ab84-b52f-4a4e-9cc2-c0f1eb973586', 'injected_plasmid', NULL, '2025-07-28 00:00:00+00', 'dk', 'robust otic expression', '2025-09-23 22:35:52.342906+00', NULL, NULL, DEFAULT, 'da4ae7c7-9993-4f7b-a54a-241882274a1f', 'pTol2-myo6b_chr2');
INSERT INTO public.treatments VALUES ('695e575f-8b62-4089-a499-fa6394ddae9b', 'injected_rna', NULL, '2025-08-12 00:00:00+00', 'dk', 'co-expression w/ plasmid', '2025-09-23 22:35:52.342906+00', NULL, NULL, DEFAULT, '595da9e1-28d5-4d72-99e9-c0b8a8bb7507', 'ptol2-elavl3-gcamp6s-rna');
INSERT INTO public.treatments VALUES ('3c1d60c9-7519-4729-bfec-8ce38e5c0d73', 'injected_rna', NULL, '2025-07-29 00:00:00+00', 'dk', 'ear labeling', '2025-09-23 22:35:52.342906+00', NULL, NULL, DEFAULT, 'b4737cd1-8bc6-4a5d-a05b-9a6acc5297d4', 'ptol2-myo6b_chr2-rna');
INSERT INTO public.treatments VALUES ('6f093192-7d81-4f9d-99bf-c407bdcf2895', 'dye', NULL, '2025-08-12 00:00:00+00', 'dk', 'membrane dye', '2025-09-23 22:35:52.342906+00', NULL, NULL, DEFAULT, '622b6bf5-721b-45d2-b2be-056a85a3b5de', 'dii');
INSERT INTO public.treatments VALUES ('a5bbf329-2cf1-4382-8aa9-170e23ed8a90', 'dye', NULL, '2025-07-29 00:00:00+00', 'dk', 'retrograde label', '2025-09-23 22:35:52.342906+00', NULL, NULL, DEFAULT, '930636fb-6e71-4c4b-8fe2-7927c84fb65e', 'fluorogold');
INSERT INTO public.treatments VALUES ('2f55740a-491e-44c0-b217-62605e90c9c3', 'injected_rna', NULL, '2025-08-12 00:00:00+00', 'dk', 'strong heart signal', '2025-09-23 22:35:52.342906+00', NULL, NULL, DEFAULT, '099ddef6-e8c1-4d4f-a98d-d0207223e13c', 'gfp-sense');
INSERT INTO public.treatments VALUES ('19493aeb-157a-42d9-8405-ec06fad9593c', 'dye', NULL, '2025-08-13 00:00:00+00', 'dk', 'optic tract labeled', '2025-09-23 22:35:52.342906+00', NULL, NULL, DEFAULT, '50cc9492-d610-421e-9c64-72db62aeeec5', 'dii');


--
-- PostgreSQL database dump complete
--

\unrestrict qfQRSj2sQojOvgn7B25cW8LTr7tRrbeNTgKVQ8fESwT29HnKlYRtTcX2sHHlwbU

