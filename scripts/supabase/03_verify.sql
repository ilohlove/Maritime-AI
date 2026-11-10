-- Read-only catalog assertions. Run as administrator after provisioning.
BEGIN READ ONLY;
DO $$
DECLARE t text; r text; p text; expected boolean; allowed text[];
BEGIN
  IF (SELECT version_num FROM public.alembic_version) IS DISTINCT FROM '0004' THEN
    RAISE EXCEPTION 'Migration head must be 0004';
  END IF;
  FOREACH r IN ARRAY ARRAY['maritime_backend','maritime_migrator'] LOOP
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname=r AND rolcanlogin
       AND NOT (rolsuper OR rolcreatedb OR rolcreaterole OR rolinherit OR rolreplication OR rolbypassrls))
       OR EXISTS (SELECT FROM pg_auth_members WHERE member=r::regrole) THEN
      RAISE EXCEPTION 'Unsafe role flags or inherited/settable membership: %', r;
    END IF;
  END LOOP;
  IF has_schema_privilege('maritime_backend','public','CREATE') THEN
    RAISE EXCEPTION 'Backend can create schema objects';
  END IF;
  FOREACH t IN ARRAY ARRAY['vessels','documents','document_chunks','auth_sessions',
                          'rate_windows','ai_daily_usage','alembic_version'] LOOP
    IF NOT EXISTS (SELECT FROM pg_class WHERE oid=to_regclass('public.'||t)
                   AND relrowsecurity AND relowner='maritime_migrator'::regrole) THEN
      RAISE EXCEPTION 'Incorrect owner/RLS on %', t;
    END IF;
    IF EXISTS (SELECT FROM pg_class c,
        LATERAL aclexplode(coalesce(c.relacl,acldefault('r',c.relowner))) a
        WHERE c.oid=to_regclass('public.'||t) AND (a.grantee=0 OR (a.grantee='maritime_backend'::regrole AND a.is_grantable))) THEN
      RAISE EXCEPTION 'PUBLIC access or backend grant option: %', t;
    END IF;
    IF (SELECT count(*) FROM pg_policies WHERE schemaname='public' AND tablename=t
        AND policyname='maritime_backend_access' AND roles=ARRAY['maritime_backend']::name[]
        AND cmd='ALL' AND qual='true' AND with_check='true') <> 1
        OR (SELECT count(*) FROM pg_policies WHERE schemaname='public' AND tablename=t) <> 1 THEN
      RAISE EXCEPTION 'Unexpected RLS policies: %', t;
    END IF;
    allowed := CASE t
      WHEN 'alembic_version' THEN ARRAY['SELECT']
      WHEN 'auth_sessions' THEN ARRAY['SELECT','INSERT','DELETE']
      WHEN 'ai_daily_usage' THEN ARRAY['SELECT','INSERT','UPDATE']
      WHEN 'document_chunks' THEN ARRAY['SELECT','INSERT','DELETE']
      ELSE ARRAY['SELECT','INSERT','UPDATE','DELETE'] END;
    FOREACH r IN ARRAY ARRAY['maritime_backend','anon','authenticated'] LOOP
      FOREACH p IN ARRAY ARRAY['SELECT','INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER'] LOOP
        expected := r='maritime_backend' AND p=ANY(allowed);
        IF has_table_privilege(r,'public.'||t,p) IS DISTINCT FROM expected THEN
          RAISE EXCEPTION 'Unexpected % privilege for % on %', p,r,t;
        END IF;
      END LOOP;
    END LOOP;
  END LOOP;
  FOREACH r IN ARRAY ARRAY['maritime_backend','anon','authenticated'] LOOP
    FOREACH p IN ARRAY ARRAY['USAGE','SELECT','UPDATE'] LOOP
      IF has_sequence_privilege(r,'public.document_chunks_id_seq',p)
         IS DISTINCT FROM (r='maritime_backend' AND p='USAGE') THEN
        RAISE EXCEPTION 'Unexpected sequence access for %: %',r,p;
      END IF;
    END LOOP;
  END LOOP;
END $$;
COMMIT;
