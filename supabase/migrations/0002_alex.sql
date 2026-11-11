ALTER TABLE messages DROP CONSTRAINT IF EXISTS messages_status_check;
-- ;;

ALTER TABLE messages ADD CONSTRAINT messages_status_check
  CHECK (status IN ('queued', 'sent', 'received', 'blocked', 'failed', 'draft'));
-- ;;

ALTER TABLE approvals DROP CONSTRAINT IF EXISTS approvals_action_type_check;
-- ;;

ALTER TABLE approvals ADD CONSTRAINT approvals_action_type_check
  CHECK (action_type IN (
    'sign_agreement', 'bind_price', 'bind_commission', 'payment',
    'banking_change', 'legal_declaration', 'share_restricted', 'send_outreach'
  ));
-- ;;

ALTER TABLE calls DROP CONSTRAINT IF EXISTS calls_status_check;
-- ;;

ALTER TABLE calls ADD CONSTRAINT calls_status_check
  CHECK (status IN ('initiated', 'in_progress', 'completed', 'failed', 'blocked', 'authorized'));
