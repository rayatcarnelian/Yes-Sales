-- YES SALES schema. Applied once per database by the migration runner.
-- Statements are separated by a line containing only: -- ;;

CREATE TABLE schema_migrations (
  version text PRIMARY KEY,
  applied_at timestamptz NOT NULL DEFAULT now()
);
-- ;;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'yes_app') THEN
    CREATE ROLE yes_app LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
  END IF;
END $$;
-- ;;

CREATE OR REPLACE FUNCTION yes_touch_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;
-- ;;

CREATE OR REPLACE FUNCTION yes_app_visible()
RETURNS boolean
LANGUAGE sql
STABLE
AS $$
  SELECT current_setting('app.role', true) IN ('founder', 'operator', 'agent')
$$;
-- ;;

CREATE OR REPLACE FUNCTION yes_guard_agreement()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF NEW.status = 'signed' THEN
    IF NEW.approval_id IS NULL THEN
      RAISE EXCEPTION 'signed agreement requires founder approval';
    END IF;
    IF NOT EXISTS (
      SELECT 1 FROM approvals
      WHERE id = NEW.approval_id
        AND status = 'approved'
        AND action_type = 'sign_agreement'
    ) THEN
      RAISE EXCEPTION 'approval is not an approved sign_agreement decision';
    END IF;
  END IF;
  RETURN NEW;
END;
$$;
-- ;;

CREATE OR REPLACE FUNCTION yes_guard_commission()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  terms_changed boolean;
BEGIN
  IF TG_OP = 'INSERT' THEN
    terms_changed := true;
  ELSE
    terms_changed := NEW.rate_percent IS DISTINCT FROM OLD.rate_percent
      OR NEW.contracted_amount IS DISTINCT FROM OLD.contracted_amount;
  END IF;
  IF terms_changed AND (NEW.rate_percent IS NOT NULL OR NEW.contracted_amount IS NOT NULL) THEN
    IF NEW.approval_id IS NULL THEN
      RAISE EXCEPTION 'commission terms require founder approval';
    END IF;
    IF NOT EXISTS (
      SELECT 1 FROM approvals
      WHERE id = NEW.approval_id
        AND status = 'approved'
        AND action_type = 'bind_commission'
    ) THEN
      RAISE EXCEPTION 'approval is not an approved bind_commission decision';
    END IF;
  END IF;
  RETURN NEW;
END;
$$;
-- ;;

CREATE TABLE users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email text NOT NULL UNIQUE,
  full_name text NOT NULL,
  role text NOT NULL CHECK (role IN ('founder', 'operator', 'agent')),
  supabase_user_id uuid UNIQUE,
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
-- ;;

CREATE TABLE user_credentials (
  user_id uuid PRIMARY KEY REFERENCES users(id),
  password_hash text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
-- ;;

CREATE TABLE companies (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  legal_name text NOT NULL,
  normalized_name text NOT NULL,
  country text NOT NULL CHECK (char_length(country) = 2),
  website text,
  website_domain text,
  role text NOT NULL CHECK (role IN ('supplier', 'buyer', 'both')),
  category text,
  verification_status text NOT NULL DEFAULT 'unverified'
    CHECK (verification_status IN ('unverified', 'evidence_recorded', 'verified', 'rejected')),
  supplier_stage text
    CHECK (supplier_stage IS NULL OR supplier_stage IN (
      'discover', 'research', 'verify', 'contact_eligible', 'introduction', 'response',
      'qualification', 'catalog', 'quotation', 'agreement_review', 'active_supplier'
    )),
  buyer_stage text
    CHECK (buyer_stage IS NULL OR buyer_stage IN (
      'discover', 'research', 'verify', 'contact_eligible', 'introduction', 'response',
      'requirements', 'qualification', 'match', 'rfq', 'deal'
    )),
  summary text,
  is_test boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (normalized_name, country)
);
-- ;;

CREATE UNIQUE INDEX companies_domain_uidx
  ON companies (website_domain)
  WHERE website_domain IS NOT NULL;
-- ;;

CREATE TABLE contacts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id uuid NOT NULL REFERENCES companies(id),
  full_name text NOT NULL,
  title text,
  channel text NOT NULL CHECK (channel IN ('email', 'phone', 'whatsapp')),
  value text NOT NULL,
  normalized_value text NOT NULL,
  is_public_business boolean NOT NULL DEFAULT true,
  source_url text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (company_id, channel, normalized_value)
);
-- ;;

CREATE TABLE contact_permissions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  contact_id uuid NOT NULL UNIQUE REFERENCES contacts(id),
  allowed boolean NOT NULL DEFAULT false,
  opted_out boolean NOT NULL DEFAULT false,
  opted_out_at timestamptz,
  consent_for_callback boolean NOT NULL DEFAULT false,
  authorization_basis text NOT NULL DEFAULT 'unknown'
    CHECK (authorization_basis IN ('public_business', 'explicit_consent', 'unknown')),
  daily_limit integer NOT NULL DEFAULT 3 CHECK (daily_limit >= 0),
  notes text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
-- ;;

CREATE TABLE research_sources (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id uuid NOT NULL REFERENCES companies(id),
  source_url text NOT NULL,
  source_title text,
  retrieved_at timestamptz NOT NULL,
  excerpt text NOT NULL,
  provider text NOT NULL CHECK (provider IN ('manual', 'mock', 'http', 'xai')),
  provider_mode text NOT NULL CHECK (provider_mode IN ('live', 'mock', 'not_configured')),
  evidence_fields jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);
-- ;;

CREATE UNIQUE INDEX research_sources_uidx
  ON research_sources (company_id, source_url, ((retrieved_at AT TIME ZONE 'UTC')::date));
-- ;;

CREATE TABLE products (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id uuid NOT NULL REFERENCES companies(id),
  name text NOT NULL,
  category text,
  specifications jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
-- ;;

CREATE TABLE product_documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  product_id uuid NOT NULL REFERENCES products(id),
  doc_type text NOT NULL,
  storage_path text NOT NULL,
  filename text NOT NULL,
  content_type text NOT NULL,
  byte_size integer NOT NULL CHECK (byte_size >= 0),
  created_at timestamptz NOT NULL DEFAULT now()
);
-- ;;

CREATE TABLE buyer_requirements (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id uuid NOT NULL REFERENCES companies(id),
  product_category text NOT NULL,
  specifications jsonb NOT NULL DEFAULT '{}'::jsonb,
  desired_quantity numeric(14, 2),
  moq_acceptable numeric(14, 2),
  destination_country text CHECK (destination_country IS NULL OR char_length(destination_country) = 2),
  required_certifications text[] NOT NULL DEFAULT '{}',
  lead_time_days integer,
  delivery_terms text,
  currency text CHECK (currency IS NULL OR char_length(currency) = 3),
  incoterms text,
  notes text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
-- ;;

CREATE TABLE opportunities (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  buyer_company_id uuid NOT NULL REFERENCES companies(id),
  supplier_company_id uuid REFERENCES companies(id),
  buyer_requirement_id uuid REFERENCES buyer_requirements(id),
  title text NOT NULL,
  stage text NOT NULL DEFAULT 'draft'
    CHECK (stage IN ('draft', 'quoting', 'negotiating', 'approval', 'won', 'lost')),
  status text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed')),
  pipeline_value numeric(14, 2) NOT NULL DEFAULT 0,
  currency text NOT NULL DEFAULT 'USD' CHECK (char_length(currency) = 3),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
-- ;;

CREATE TABLE rfqs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  buyer_requirement_id uuid NOT NULL REFERENCES buyer_requirements(id),
  opportunity_id uuid REFERENCES opportunities(id),
  status text NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft', 'sent', 'quoted', 'negotiating', 'closed')),
  notes text,
  requested_samples jsonb NOT NULL DEFAULT '[]'::jsonb,
  requested_documents jsonb NOT NULL DEFAULT '[]'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
-- ;;

CREATE TABLE supplier_offers (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id uuid NOT NULL REFERENCES companies(id),
  product_id uuid REFERENCES products(id),
  rfq_id uuid REFERENCES rfqs(id),
  version integer NOT NULL CHECK (version >= 1),
  unit_price numeric(14, 4),
  currency text CHECK (currency IS NULL OR char_length(currency) = 3),
  incoterms text,
  moq numeric(14, 2),
  capacity numeric(14, 2),
  lead_time_days integer,
  origin_country text CHECK (origin_country IS NULL OR char_length(origin_country) = 2),
  certifications text[] NOT NULL DEFAULT '{}',
  delivery_terms text,
  valid_until date,
  notes text,
  created_at timestamptz NOT NULL DEFAULT now()
);
-- ;;

CREATE UNIQUE INDEX supplier_offers_version_uidx
  ON supplier_offers (company_id, rfq_id, version)
  WHERE rfq_id IS NOT NULL;
-- ;;

CREATE TABLE conversations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id uuid NOT NULL REFERENCES companies(id),
  contact_id uuid NOT NULL REFERENCES contacts(id),
  channel text NOT NULL CHECK (channel IN ('email', 'phone', 'whatsapp')),
  subject text,
  status text NOT NULL DEFAULT 'open'
    CHECK (status IN ('open', 'waiting', 'handoff', 'closed')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
-- ;;

CREATE TABLE messages (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id uuid NOT NULL REFERENCES conversations(id),
  direction text NOT NULL CHECK (direction IN ('inbound', 'outbound')),
  channel text NOT NULL CHECK (channel IN ('email', 'phone', 'whatsapp')),
  body text NOT NULL,
  classification text,
  provider_mode text NOT NULL CHECK (provider_mode IN ('live', 'mock', 'not_configured')),
  external_id text,
  status text NOT NULL CHECK (status IN ('queued', 'sent', 'received', 'blocked', 'failed')),
  created_at timestamptz NOT NULL DEFAULT now()
);
-- ;;

CREATE TABLE calls (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id uuid REFERENCES companies(id),
  contact_id uuid REFERENCES contacts(id),
  direction text NOT NULL CHECK (direction IN ('inbound', 'outbound')),
  mode text NOT NULL CHECK (mode IN ('buyer', 'supplier')),
  provider_mode text NOT NULL CHECK (provider_mode IN ('live', 'mock', 'not_configured')),
  status text NOT NULL CHECK (status IN ('initiated', 'in_progress', 'completed', 'failed', 'blocked')),
  transcript text,
  summary text,
  consent_checked boolean NOT NULL DEFAULT false,
  external_id text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
-- ;;

CREATE TABLE matches (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  opportunity_id uuid NOT NULL REFERENCES opportunities(id),
  buyer_requirement_id uuid NOT NULL REFERENCES buyer_requirements(id),
  supplier_offer_id uuid NOT NULL REFERENCES supplier_offers(id),
  score numeric(6, 4) NOT NULL,
  confidence_cap numeric(6, 4) NOT NULL,
  explanation jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
-- ;;

CREATE TABLE approvals (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  action_type text NOT NULL CHECK (action_type IN (
    'sign_agreement', 'bind_price', 'bind_commission', 'payment',
    'banking_change', 'legal_declaration', 'share_restricted'
  )),
  status text NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'approved', 'rejected', 'expired')),
  requested_by uuid NOT NULL REFERENCES users(id),
  decided_by uuid REFERENCES users(id),
  subject_type text NOT NULL,
  subject_id uuid NOT NULL,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  notes text,
  decision_note text,
  created_at timestamptz NOT NULL DEFAULT now(),
  decided_at timestamptz
);
-- ;;

CREATE TABLE agreements (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  opportunity_id uuid NOT NULL UNIQUE REFERENCES opportunities(id),
  status text NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft', 'pending_approval', 'signed', 'rejected')),
  terms jsonb NOT NULL DEFAULT '{}'::jsonb,
  evidence_note text,
  approval_id uuid REFERENCES approvals(id),
  signed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
-- ;;

CREATE TABLE commission_records (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  opportunity_id uuid NOT NULL REFERENCES opportunities(id),
  agreement_id uuid REFERENCES agreements(id),
  terms_text text,
  rate_percent numeric(7, 4),
  contracted_amount numeric(14, 2),
  collected_amount numeric(14, 2) NOT NULL DEFAULT 0,
  currency text NOT NULL DEFAULT 'USD' CHECK (char_length(currency) = 3),
  collection_status text NOT NULL DEFAULT 'none'
    CHECK (collection_status IN ('none', 'invoiced', 'partial', 'collected')),
  invoice_reference text,
  approval_id uuid REFERENCES approvals(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
-- ;;

CREATE TABLE agent_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_name text NOT NULL,
  task_id uuid,
  status text NOT NULL CHECK (status IN ('queued', 'running', 'succeeded', 'failed')),
  input jsonb NOT NULL DEFAULT '{}'::jsonb,
  output jsonb,
  error text,
  cost_usd numeric(12, 6) NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz
);
-- ;;

CREATE TABLE tasks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  task_type text NOT NULL,
  idempotency_key text NOT NULL UNIQUE,
  status text NOT NULL DEFAULT 'queued'
    CHECK (status IN ('queued', 'running', 'succeeded', 'failed', 'dead', 'cancelled')),
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  attempt integer NOT NULL DEFAULT 0,
  max_attempts integer NOT NULL DEFAULT 5 CHECK (max_attempts >= 1),
  next_run_at timestamptz NOT NULL DEFAULT now(),
  deadline_at timestamptz,
  last_error text,
  result jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
-- ;;

ALTER TABLE agent_runs
  ADD CONSTRAINT agent_runs_task_fk FOREIGN KEY (task_id) REFERENCES tasks(id);
-- ;;

CREATE TABLE audit_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  actor_id uuid REFERENCES users(id),
  action text NOT NULL,
  entity_type text NOT NULL,
  entity_id uuid,
  detail jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);
-- ;;

CREATE TABLE webhook_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  provider text NOT NULL,
  signature_valid boolean NOT NULL,
  payload jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
-- ;;

CREATE TABLE notification_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid REFERENCES users(id),
  kind text NOT NULL,
  title text NOT NULL,
  body text NOT NULL,
  read_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);
-- ;;

CREATE TABLE provider_usage (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  provider text NOT NULL,
  mode text NOT NULL CHECK (mode IN ('live', 'mock', 'not_configured')),
  operation text NOT NULL,
  units numeric(12, 4) NOT NULL DEFAULT 1,
  cost_usd numeric(12, 6) NOT NULL DEFAULT 0,
  agent_run_id uuid REFERENCES agent_runs(id),
  created_at timestamptz NOT NULL DEFAULT now()
);
-- ;;

CREATE TABLE operating_settings (
  id integer PRIMARY KEY CHECK (id = 1),
  outbound_paused boolean NOT NULL DEFAULT false,
  budget_ceiling_usd numeric(12, 2) NOT NULL DEFAULT 25,
  budget_spent_usd numeric(12, 6) NOT NULL DEFAULT 0,
  updated_at timestamptz NOT NULL DEFAULT now()
);
-- ;;

INSERT INTO operating_settings (id, outbound_paused, budget_ceiling_usd, budget_spent_usd)
VALUES (1, false, 25, 0);
-- ;;

CREATE INDEX companies_role_idx ON companies (role, verification_status);
-- ;;
CREATE INDEX companies_country_idx ON companies (country, category);
-- ;;
CREATE INDEX contacts_company_idx ON contacts (company_id);
-- ;;
CREATE INDEX messages_conversation_idx ON messages (conversation_id, created_at);
-- ;;
CREATE INDEX tasks_due_idx ON tasks (status, next_run_at);
-- ;;
CREATE INDEX approvals_status_idx ON approvals (status, action_type);
-- ;;
CREATE INDEX audit_entity_idx ON audit_events (entity_type, entity_id, created_at);
-- ;;
CREATE INDEX opportunities_buyer_idx ON opportunities (buyer_company_id);
-- ;;
CREATE INDEX agent_runs_status_idx ON agent_runs (status);
-- ;;
CREATE INDEX calls_mode_idx ON calls (provider_mode, created_at);
-- ;;

CREATE TRIGGER users_touch BEFORE UPDATE ON users
  FOR EACH ROW EXECUTE FUNCTION yes_touch_updated_at();
-- ;;
CREATE TRIGGER companies_touch BEFORE UPDATE ON companies
  FOR EACH ROW EXECUTE FUNCTION yes_touch_updated_at();
-- ;;
CREATE TRIGGER contacts_touch BEFORE UPDATE ON contacts
  FOR EACH ROW EXECUTE FUNCTION yes_touch_updated_at();
-- ;;
CREATE TRIGGER contact_permissions_touch BEFORE UPDATE ON contact_permissions
  FOR EACH ROW EXECUTE FUNCTION yes_touch_updated_at();
-- ;;
CREATE TRIGGER products_touch BEFORE UPDATE ON products
  FOR EACH ROW EXECUTE FUNCTION yes_touch_updated_at();
-- ;;
CREATE TRIGGER buyer_requirements_touch BEFORE UPDATE ON buyer_requirements
  FOR EACH ROW EXECUTE FUNCTION yes_touch_updated_at();
-- ;;
CREATE TRIGGER opportunities_touch BEFORE UPDATE ON opportunities
  FOR EACH ROW EXECUTE FUNCTION yes_touch_updated_at();
-- ;;
CREATE TRIGGER rfqs_touch BEFORE UPDATE ON rfqs
  FOR EACH ROW EXECUTE FUNCTION yes_touch_updated_at();
-- ;;
CREATE TRIGGER conversations_touch BEFORE UPDATE ON conversations
  FOR EACH ROW EXECUTE FUNCTION yes_touch_updated_at();
-- ;;
CREATE TRIGGER calls_touch BEFORE UPDATE ON calls
  FOR EACH ROW EXECUTE FUNCTION yes_touch_updated_at();
-- ;;
CREATE TRIGGER agreements_touch BEFORE UPDATE ON agreements
  FOR EACH ROW EXECUTE FUNCTION yes_touch_updated_at();
-- ;;
CREATE TRIGGER commission_records_touch BEFORE UPDATE ON commission_records
  FOR EACH ROW EXECUTE FUNCTION yes_touch_updated_at();
-- ;;
CREATE TRIGGER tasks_touch BEFORE UPDATE ON tasks
  FOR EACH ROW EXECUTE FUNCTION yes_touch_updated_at();
-- ;;
CREATE TRIGGER operating_settings_touch BEFORE UPDATE ON operating_settings
  FOR EACH ROW EXECUTE FUNCTION yes_touch_updated_at();
-- ;;
CREATE TRIGGER agreements_guard BEFORE INSERT OR UPDATE ON agreements
  FOR EACH ROW EXECUTE FUNCTION yes_guard_agreement();
-- ;;
CREATE TRIGGER commission_records_guard BEFORE INSERT OR UPDATE ON commission_records
  FOR EACH ROW EXECUTE FUNCTION yes_guard_commission();
-- ;;

DO $$
DECLARE
  t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'users', 'companies', 'contacts', 'contact_permissions', 'research_sources',
    'products', 'product_documents', 'buyer_requirements', 'supplier_offers',
    'conversations', 'messages', 'calls', 'rfqs', 'opportunities', 'matches',
    'agreements', 'commission_records', 'agent_runs', 'tasks', 'approvals',
    'audit_events', 'webhook_events', 'notification_events', 'provider_usage',
    'operating_settings'
  ]
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
-- ;;

ALTER TABLE user_credentials ENABLE ROW LEVEL SECURITY;
-- ;;
ALTER TABLE user_credentials FORCE ROW LEVEL SECURITY;
-- ;;
ALTER TABLE schema_migrations ENABLE ROW LEVEL SECURITY;
-- ;;
ALTER TABLE schema_migrations FORCE ROW LEVEL SECURITY;
-- ;;
GRANT USAGE ON SCHEMA public TO yes_app;
