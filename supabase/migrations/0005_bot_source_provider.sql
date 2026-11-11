DO $$
DECLARE
  constraint_name text;
BEGIN
  FOR constraint_name IN
    SELECT con.conname
    FROM pg_constraint con
    JOIN pg_class rel ON rel.oid = con.conrelid
    WHERE rel.relname = 'research_sources'
      AND con.contype = 'c'
      AND pg_get_constraintdef(con.oid) ILIKE '%provider%'
  LOOP
    EXECUTE format('ALTER TABLE research_sources DROP CONSTRAINT %I', constraint_name);
  END LOOP;
END $$;
-- ;;

ALTER TABLE research_sources
  ADD CONSTRAINT research_sources_provider_check
  CHECK (provider IN ('manual', 'mock', 'http', 'xai', 'bot'));
