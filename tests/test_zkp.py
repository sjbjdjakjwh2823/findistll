import unittest

from app.services.zkp_validator import ZKPValidator


class ZKPValidatorTests(unittest.TestCase):
    def test_verify_accounting_proof_with_relation_hash(self):
        validator = ZKPValidator()
        revenue = 1250
        expenses = 400
        net_income = revenue - expenses

        relation_payload = {
            "revenue": revenue,
            "expenses": expenses,
            "net_income": net_income,
        }
        relation_hash = validator._hash_obj(relation_payload)

        proof = {
            "pi_a": ["0x01", "0x02"],
            "pi_b": [["0x03", "0x04"], ["0x05", "0x06"]],
            "pi_c": ["0x07", "0x08"],
            "relation_hash": relation_hash,
            "revenue_commitment": validator._hash_obj({"revenue": revenue}),
            "expenses_commitment": validator._hash_obj({"expenses": expenses}),
        }
        public_signals = [net_income]
        verification_key = {
            "protocol": "groth16",
            "circuit_id": "integrity_check",
            "expected_relation_hash": relation_hash,
        }

        result = validator.verify_accounting_proof(
            proof=proof,
            public_signals=public_signals,
            verification_key=verification_key,
            scheme="groth16",
        )

        self.assertTrue(result["valid"])
        self.assertEqual(result["status"], "verified")
        self.assertTrue(result["checks"].get("relation_hash_match"))
        self.assertTrue(result["checks"].get("commitments_present"))


if __name__ == "__main__":
    unittest.main()
