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
