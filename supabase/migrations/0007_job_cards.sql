CREATE TABLE service_sheets (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id uuid NOT NULL REFERENCES companies(id),
  service_name text NOT NULL,
  duration_notes text,
  currency text NOT NULL DEFAULT 'MYR',
  price numeric(14, 2) NOT NULL,
  status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'approved')),
  allowed_sentence text NOT NULL,
  approval_id uuid REFERENCES approvals(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
-- ;;

CREATE INDEX service_sheets_company_idx ON service_sheets (company_id, status);
-- ;;

CREATE TABLE job_cards (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id uuid NOT NULL REFERENCES companies(id),
  contact_id uuid REFERENCES contacts(id),
  vehicle text NOT NULL,
  requested_service text NOT NULL,
  preferred_time text,
  photo_note text,
  status text NOT NULL DEFAULT 'requested'
    CHECK (status IN ('requested', 'handed_off', 'price_approved', 'bay_confirmed', 'declined')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
-- ;;

CREATE INDEX job_cards_company_idx ON job_cards (company_id, created_at DESC);
-- ;;

CREATE TABLE job_card_replies (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  job_card_id uuid NOT NULL REFERENCES job_cards(id),
  body text NOT NULL,
  sent boolean NOT NULL DEFAULT false CHECK (sent = false),
  allowed_sheet_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
  price_allowed boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now()
);
-- ;;

CREATE INDEX job_card_replies_card_idx ON job_card_replies (job_card_id, created_at DESC);
-- ;;

CREATE OR REPLACE FUNCTION yes_guard_service_sheet()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF NEW.status = 'approved' THEN
    IF NEW.approval_id IS NULL OR NOT EXISTS (
      SELECT 1 FROM approvals
      WHERE id = NEW.approval_id
        AND subject_type = 'service_sheet'
        AND subject_id = NEW.id
        AND action_type = 'bind_price'
        AND status = 'approved'
    ) THEN
      RAISE EXCEPTION 'service sheet price requires founder approval';
    END IF;
  END IF;
  RETURN NEW;
END;
$$;
-- ;;

CREATE TRIGGER service_sheets_guard
  BEFORE INSERT OR UPDATE ON service_sheets
  FOR EACH ROW EXECUTE FUNCTION yes_guard_service_sheet();
-- ;;

CREATE TRIGGER service_sheets_touch BEFORE UPDATE ON service_sheets
  FOR EACH ROW EXECUTE FUNCTION yes_touch_updated_at();
-- ;;

CREATE OR REPLACE FUNCTION yes_guard_job_card()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF NEW.status IN ('bay_confirmed', 'price_approved') AND NOT EXISTS (
    SELECT 1 FROM approvals
    WHERE subject_type = 'job_card'
      AND subject_id = NEW.id
      AND action_type = 'bind_price'
      AND status = 'approved'
  ) THEN
    RAISE EXCEPTION 'job card confirmation requires founder approval';
  END IF;
  RETURN NEW;
END;
$$;
-- ;;

CREATE TRIGGER job_cards_guard
  BEFORE INSERT OR UPDATE ON job_cards
  FOR EACH ROW EXECUTE FUNCTION yes_guard_job_card();
-- ;;

CREATE TRIGGER job_cards_touch BEFORE UPDATE ON job_cards
  FOR EACH ROW EXECUTE FUNCTION yes_touch_updated_at();
-- ;;

DO $$
DECLARE
  t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['service_sheets', 'job_cards', 'job_card_replies']
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
