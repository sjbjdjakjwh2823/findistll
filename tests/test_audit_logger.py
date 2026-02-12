
import unittest
import os

from app.core.audit_logger import AuditLogger

class TestAuditLogger(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Ensure SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are set for testing
        # In a real test, you'd use a test-specific Supabase instance or mock it.
        if not os.environ.get("SUPABASE_URL"):
            os.environ["SUPABASE_URL"] = "https://nnuixqxmalttautcqckt.supabase.co"
        if not os.environ.get("SUPABASE_SERVICE_ROLE_KEY"):
            os.environ["SUPABASE_SERVICE_ROLE_KEY"] = "REDACTED_SUPABASE_SERVICE_ROLE_KEY"

        cls.logger = AuditLogger()
        cls.test_actor_id = "test_human_123"
        cls.test_entity_id = "test_document_456"
        cls.test_action_type = "document_viewed"

    def test_log_action(self):
        print("\n--- Testing log_action ---")
        initial_logs = self.logger.get_audit_logs_by_actor(self.test_actor_id)
        initial_count = len(initial_logs)
        print(f"Initial logs for {self.test_actor_id}: {initial_count}")

        # Log an action
        self.logger.log_action(
            actor_type="human",
            actor_id=self.test_actor_id,
            action_type=self.test_action_type,
            entity_type="document",
            entity_id=self.test_entity_id,
            details={
                "document_name": "Preciso Master Plan",
                "ip_address": "192.168.1.1",
                "user_agent": "test-browser"
            }
        )
        print("Logged a test action.")

        # Verify it was logged
        retrieved_logs = self.logger.get_audit_logs_by_actor(self.test_actor_id)
        print(f"Logs after logging: {len(retrieved_logs)}")
        self.assertEqual(len(retrieved_logs), initial_count + 1)

        # Check content of the last log entry
        last_log = retrieved_logs[0]
        self.assertEqual(last_log["actor_type"], "human")
        self.assertEqual(last_log["actor_id"], self.test_actor_id)
        self.assertEqual(last_log["action_type"], self.test_action_type)
        self.assertEqual(last_log["entity_type"], "document")
        self.assertEqual(last_log["entity_id"], self.test_entity_id)
        self.assertTrue(last_log["is_immutable"])
        print("Log content verified successfully.")

    def test_get_all_audit_logs(self):
        print("\n--- Testing get_audit_logs (all) ---")
        logs = self.logger.get_audit_logs(limit=5)
        print(f"Retrieved {len(logs)} total audit logs (limit 5).")
        self.assertIsInstance(logs, list)

    def test_get_audit_logs_by_entity(self):
        print("\n--- Testing get_audit_logs_by_entity ---")
        # Log another action for a different entity to ensure filtering works
        self.logger.log_action(
            actor_type="ai",
            actor_id="ai_agent_epsilon",
            action_type="data_processed",
            entity_type="data_source",
            entity_id="financial_feed_alpha",
            details={
                "records_processed": 1000,
                "model_version": "v2.1"
            }
        )
        print("Logged an AI action for a different entity.")

        entity_logs = self.logger.get_audit_logs_by_entity("financial_feed_alpha")
        print(f"Retrieved {len(entity_logs)} logs for entity 'financial_feed_alpha'.")
        self.assertTrue(len(entity_logs) >= 1)
        for log in entity_logs:
            self.assertEqual(log["entity_id"], "financial_feed_alpha")
        print("Entity-specific log retrieval verified.")


if __name__ == '__main__':
    # Before running tests, ensure the Supabase 'audit_logs' table is created
    # and RLS policies are applied as defined in preciso/supabase_audit_logs.sql.
    # For local development/testing, you might run this SQL manually in your Supabase UI.
    print("\n*** IMPORTANT: Ensure Supabase 'audit_logs' table and RLS policies are set up! ***")
    print("*** Please execute the SQL in preciso/supabase_audit_logs.sql manually in your Supabase project. ***")
    unittest.main(exit=False)
