CREATE TABLE commercial_audit_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  environment text NOT NULL,
  database_name text NOT NULL,
  status text NOT NULL CHECK (status IN ('passed', 'failed', 'completed_with_gaps')),
  started_at timestamptz NOT NULL,
  finished_at timestamptz NOT NULL,
  summary jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
-- ;;

CREATE TABLE commercial_audit_cases (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id uuid NOT NULL REFERENCES commercial_audit_runs(id),
  code text NOT NULL,
  title text NOT NULL,
  status text NOT NULL CHECK (status IN ('passed', 'failed', 'mocked', 'skipped')),
  executed_at timestamptz NOT NULL,
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  failure_reason text,
  created_at timestamptz NOT NULL DEFAULT now()
);
-- ;;

CREATE TABLE alex_outcome_metrics (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id uuid REFERENCES conversations(id),
  message_id uuid REFERENCES messages(id),
  call_id uuid REFERENCES calls(id),
  actor_kind text NOT NULL CHECK (actor_kind IN ('ai', 'human', 'system', 'test')),
  classification text,
  classification_method text,
  provider_mode text NOT NULL CHECK (provider_mode IN ('live', 'mock', 'not_configured')),
  outcome text NOT NULL,
  human_decision text,
  intervention_seconds numeric(12, 3),
  cost_usd numeric(12, 6) NOT NULL DEFAULT 0,
  comparable boolean NOT NULL DEFAULT false,
  detail jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);
-- ;;

DO $$
DECLARE
  t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['commercial_audit_runs', 'commercial_audit_cases', 'alex_outcome_metrics']
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
