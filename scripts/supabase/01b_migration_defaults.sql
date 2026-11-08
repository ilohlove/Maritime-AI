-- Run as maritime_migrator BEFORE migrations, not as a managed administrator.
BEGIN;
DO $$ BEGIN
  IF current_user <> 'maritime_migrator' THEN
    RAISE EXCEPTION 'Connect as maritime_migrator';
  END IF;
END $$;
-- Schema-specific revokes alone cannot remove global default grants.
ALTER DEFAULT PRIVILEGES FOR ROLE maritime_migrator
  REVOKE ALL ON TABLES FROM PUBLIC, anon, authenticated, maritime_backend;
ALTER DEFAULT PRIVILEGES FOR ROLE maritime_migrator IN SCHEMA public
  REVOKE ALL ON TABLES FROM PUBLIC, anon, authenticated, maritime_backend;
ALTER DEFAULT PRIVILEGES FOR ROLE maritime_migrator
  REVOKE ALL ON SEQUENCES FROM PUBLIC, anon, authenticated, maritime_backend;
ALTER DEFAULT PRIVILEGES FOR ROLE maritime_migrator IN SCHEMA public
  REVOKE ALL ON SEQUENCES FROM PUBLIC, anon, authenticated, maritime_backend;
ALTER DEFAULT PRIVILEGES FOR ROLE maritime_migrator
  REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC, anon, authenticated, maritime_backend;
ALTER DEFAULT PRIVILEGES FOR ROLE maritime_migrator IN SCHEMA public
  REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC, anon, authenticated, maritime_backend;
COMMIT;
