ALTER TABLE bot_imports DROP CONSTRAINT IF EXISTS bot_imports_task_id_key;
-- ;;

ALTER TABLE bot_imports
  ADD COLUMN IF NOT EXISTS claim_evidence jsonb NOT NULL DEFAULT '{}'::jsonb;
-- ;;

CREATE UNIQUE INDEX IF NOT EXISTS bot_imports_task_company_uidx
  ON bot_imports (task_id, lower(company_identity), COALESCE(country, ''));
-- ;;

ALTER TABLE operating_settings
  ADD COLUMN IF NOT EXISTS jobs_paused boolean NOT NULL DEFAULT false;
