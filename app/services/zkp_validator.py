import hashlib
import json
from typing import Any, Dict, List, Optional


class ZKPValidator:
    """
    Mock ZKP verification for SnarkJS/Circom proofs.

    This simulates Groth16/Plonk verification by validating proof structure and
    comparing deterministic hashes when expected values are provided.
    """

    def __init__(self, supported_schemes: Optional[List[str]] = None) -> None:
        schemes = supported_schemes or ["groth16", "plonk"]
        self.supported_schemes = {scheme.lower() for scheme in schemes}

    def verify_proof(
        self,
        proof: Dict[str, Any],
        public_signals: List[Any],
        verification_key: Dict[str, Any],
        scheme: str = "groth16",
        circuit_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        scheme_normalized = (scheme or "groth16").lower().strip()
        errors: List[str] = []

        if scheme_normalized not in self.supported_schemes:
            errors.append(f"unsupported_scheme:{scheme_normalized}")

        if not isinstance(proof, dict):
            errors.append("proof_invalid_type")
            proof = {}
        if not isinstance(public_signals, list):
            errors.append("public_signals_invalid_type")
            public_signals = []
        if not isinstance(verification_key, dict):
            errors.append("verification_key_invalid_type")
            verification_key = {}

        if not public_signals:
            errors.append("public_signals_empty")

        missing_fields = self._missing_fields(proof, scheme_normalized)
        if missing_fields:
            errors.append(f"proof_missing_fields:{','.join(missing_fields)}")

        vk_protocol = str(verification_key.get("protocol") or "").lower().strip()
        if vk_protocol and vk_protocol != scheme_normalized:
            errors.append("verification_key_protocol_mismatch")

        circuit = circuit_id or verification_key.get("circuit_id") or "unknown"
        proof_hash = self._hash_obj(proof)
        signals_hash = self._hash_obj(public_signals)
        vk_hash = self._hash_obj(verification_key)

        checks: Dict[str, bool] = {}
        expected_proof_hash = verification_key.get("expected_proof_hash") or verification_key.get("proof_hash")
        if expected_proof_hash:
            checks["proof_hash_match"] = expected_proof_hash == proof_hash

        expected_public_hash = verification_key.get("public_signal_hash") or proof.get("public_signal_hash")
        if expected_public_hash:
            checks["public_signal_hash_match"] = expected_public_hash == signals_hash

        expected_vk_hash = verification_key.get("vk_hash")
        if expected_vk_hash:
            checks["vk_hash_match"] = expected_vk_hash == vk_hash

        if not checks:
            checks["structure_only"] = True

        valid = not errors and all(checks.values())
        return {
            "valid": valid,
            "status": "verified" if valid else "invalid",
            "scheme": scheme_normalized,
            "circuit_id": circuit,
            "proof_hash": proof_hash,
            "signals_hash": signals_hash,
            "vk_hash": vk_hash,
            "checks": checks,
            "errors": errors,
        }

    def verify_accounting_proof(
        self,
        proof: Dict[str, Any],
        public_signals: List[Any],
        verification_key: Dict[str, Any],
        scheme: str = "groth16",
    ) -> Dict[str, Any]:
        """
        Verify the IntegrityCheck circuit: Revenue - Expenses = Net Income.

        This mock verifier expects net income as the first public signal and
        optionally checks a relation hash for private inputs.
        """
        result = self.verify_proof(
            proof=proof,
            public_signals=public_signals,
            verification_key=verification_key,
            scheme=scheme,
            circuit_id="integrity_check",
        )

        extra_errors: List[str] = []
        extra_checks: Dict[str, bool] = {}

        net_income = public_signals[0] if public_signals else None
        if net_income is None:
            extra_errors.append("net_income_missing")

        expected_relation_hash = (
            verification_key.get("expected_relation_hash")
            or verification_key.get("relation_hash")
        )
        if expected_relation_hash:
            actual_relation_hash = proof.get("relation_hash")
            if actual_relation_hash is None:
                extra_errors.append("relation_hash_missing")
            extra_checks["relation_hash_match"] = actual_relation_hash == expected_relation_hash

        revenue = proof.get("revenue")
        expenses = proof.get("expenses")
        if revenue is not None and expenses is not None and net_income is not None:
            try:
                computed = float(revenue) - float(expenses)
                extra_checks["arithmetic_match"] = float(net_income) == computed
            except (TypeError, ValueError):
                extra_errors.append("arithmetic_type_error")
        elif "revenue_commitment" in proof and "expenses_commitment" in proof:
            extra_checks["commitments_present"] = True

        result["errors"].extend(extra_errors)
        result["checks"].update(extra_checks)
        result["valid"] = result["valid"] and not extra_errors and all(extra_checks.values() or [True])
        result["status"] = "verified" if result["valid"] else "invalid"
        return result

    def _missing_fields(self, proof: Dict[str, Any], scheme: str) -> List[str]:
        required = self._required_fields_for_scheme(scheme)
        if not required:
            return []
        present = {str(key).lower() for key in proof.keys()}
        return [field for field in required if field.lower() not in present]

    @staticmethod
    def _required_fields_for_scheme(scheme: str) -> List[str]:
        if scheme == "plonk":
            return ["a", "b", "c", "z", "t1", "t2", "t3"]
        return ["pi_a", "pi_b", "pi_c"]

    @staticmethod
    def _hash_obj(value: Any) -> str:
        serialized = json.dumps(value, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()
