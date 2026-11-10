-- Run as the staging project administrator, never the runtime login.
-- Passwords are deliberately absent; use psql \password interactively afterward.
BEGIN;
DO $$
DECLARE role_name text;
BEGIN
  FOREACH role_name IN ARRAY ARRAY['maritime_migrator', 'maritime_backend'] LOOP
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = role_name) THEN
      EXECUTE format('CREATE ROLE %I LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS', role_name);
    END IF;
    IF EXISTS (SELECT FROM pg_roles WHERE rolname = role_name AND
       (rolsuper OR rolcreatedb OR rolcreaterole OR rolinherit OR rolreplication OR rolbypassrls OR NOT rolcanlogin))
       OR EXISTS (SELECT FROM pg_auth_members m JOIN pg_roles r ON r.oid=m.member WHERE r.rolname=role_name)
       OR EXISTS (SELECT FROM pg_auth_members m JOIN pg_roles r ON r.oid=m.roleid WHERE r.rolname=role_name
          AND NOT (m.member=current_user::regrole AND m.admin_option)) THEN
      RAISE EXCEPTION 'Unsafe existing role or membership: %; review manually', role_name;
    END IF;
  END LOOP;
END $$;
-- Dedicated staging project only: prevent implicit schema DDL via PUBLIC.
REVOKE CREATE ON SCHEMA public FROM PUBLIC, maritime_backend;
GRANT USAGE, CREATE ON SCHEMA public TO maritime_migrator;
GRANT USAGE ON SCHEMA public TO maritime_backend;
ALTER ROLE maritime_migrator SET search_path = public;
ALTER ROLE maritime_backend SET search_path = public;
ALTER ROLE maritime_backend SET statement_timeout = '10s';
ALTER ROLE maritime_backend SET lock_timeout = '5s';
COMMIT;
