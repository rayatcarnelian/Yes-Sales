CREATE TABLE bot_imports (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  task_id text NOT NULL UNIQUE,
  agent_name text NOT NULL,
  company_id uuid REFERENCES companies(id),
  research_source_id uuid REFERENCES research_sources(id),
  company_identity text NOT NULL,
  company_type text NOT NULL,
  country text,
  product_category text,
  source_urls jsonb NOT NULL DEFAULT '[]'::jsonb,
  verification_date date,
  claimed_verification_status text,
  stored_verification_status text,
  contact_eligibility text,
  source_document_reference text,
  import_status text NOT NULL
    CHECK (import_status IN ('accepted', 'rejected', 'duplicate', 'quarantined', 'superseded')),
  rejection_reason text,
  created_at timestamptz NOT NULL DEFAULT now()
);
-- ;;

CREATE INDEX bot_imports_company_idx ON bot_imports (company_id);
-- ;;

DO $$
DECLARE
  t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['bot_imports']
  LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
    EXECUTE format('DROP POLICY IF EXISTS yes_app_access ON %I', t);
    EXECUTE format(
      'CREATE POLICY yes_app_access ON %I FOR ALL USING (yes_app_visible()) WITH CHECK (yes_app_visible())',
      t
    );
    EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON %I TO yes_app', t);
  END LOOP;
END $$;
