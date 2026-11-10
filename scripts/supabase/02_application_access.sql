-- Run as maritime_migrator AFTER upgrading to 0004, before starting a backend.
-- Reapply after every schema upgrade; no blanket future-table grants.
BEGIN;
DO $$
DECLARE t text; allowed text;
BEGIN
  IF current_user <> 'maritime_migrator' THEN
    RAISE EXCEPTION 'Connect as maritime_migrator';
  END IF;
  IF (SELECT version_num FROM public.alembic_version) IS DISTINCT FROM '0004' THEN
    RAISE EXCEPTION 'Expected migration 0004';
  END IF;
  FOREACH t IN ARRAY ARRAY['vessels','documents','document_chunks','auth_sessions',
                          'rate_windows','ai_daily_usage','alembic_version'] LOOP
    IF NOT EXISTS (SELECT FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
      WHERE n.nspname='public' AND c.relname=t AND c.relowner=current_user::regrole) THEN
      RAISE EXCEPTION 'Unexpected table owner: %', t;
    END IF;
    IF EXISTS (SELECT FROM pg_policies WHERE schemaname='public' AND tablename=t
               AND policyname <> 'maritime_backend_access') THEN
      RAISE EXCEPTION 'Unexpected policy on %; review manually', t;
    END IF;
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('REVOKE ALL ON TABLE public.%I FROM PUBLIC, anon, authenticated, maritime_backend', t);
    allowed := CASE t
      WHEN 'alembic_version' THEN 'SELECT'
      WHEN 'auth_sessions' THEN 'SELECT, INSERT, DELETE'
      WHEN 'ai_daily_usage' THEN 'SELECT, INSERT, UPDATE'
      WHEN 'document_chunks' THEN 'SELECT, INSERT, DELETE'
      ELSE 'SELECT, INSERT, UPDATE, DELETE' END;
    EXECUTE format('GRANT %s ON TABLE public.%I TO maritime_backend', allowed, t);
    EXECUTE format('DROP POLICY IF EXISTS maritime_backend_access ON public.%I', t);
    -- Backend enforces HTTP ownership; this is NOT per-tenant database RLS.
    EXECUTE format('CREATE POLICY maritime_backend_access ON public.%I TO maritime_backend USING (true) WITH CHECK (true)', t);
  END LOOP;
END $$;
-- 0001-0004 create exactly one SERIAL sequence; UUID/string keys need none.
REVOKE ALL ON SEQUENCE public.document_chunks_id_seq FROM PUBLIC, anon, authenticated, maritime_backend;
GRANT USAGE ON SEQUENCE public.document_chunks_id_seq TO maritime_backend;
COMMIT;
