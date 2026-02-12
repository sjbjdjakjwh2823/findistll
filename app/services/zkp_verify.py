"""
ZKP Verification Utilities

This module provides a ZKPVerify class that simulates a Zero-Knowledge Proof
for data integrity using a SHA-256 Merkle tree approach. The implementation
focuses on high-security standards and avoids external dependencies.

Context: Financial data integrity in a B2B setting.
"""

from __future__ import annotations

import hashlib
from typing import Iterable, List, Tuple, Dict, Any


class ZKPVerify:
    """
    Simulates Zero-Knowledge Proofs for data integrity using a Merkle tree.

    The class allows:
      - commitment creation (Merkle root)
      - proof generation for a specific record
      - proof verification without revealing other records

    Note: This is a *simulation* of ZKP-style integrity checks using standard
    cryptographic commitments (Merkle roots), not a full ZKP protocol.
    """

    def __init__(self) -> None:
        self._leaves: List[str] = []
        self._tree: List[List[str]] = []  # levels from leaves to root

    @staticmethod
    def _hash(data: bytes) -> str:
        """Return SHA-256 hash hex digest of input bytes."""
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def _hash_pair(left: str, right: str) -> str:
        """
        Hash a pair of hex digests in a deterministic order (left|right).
        """
        return ZKPVerify._hash((left + right).encode("utf-8"))

    @staticmethod
    def _normalize_record(record: Any) -> bytes:
        """
        Normalize a record into bytes safely and deterministically.
        Accepts bytes, str, int, float, or objects with __str__.
        """
        if isinstance(record, bytes):
            return record
        if isinstance(record, str):
            return record.encode("utf-8")
        if isinstance(record, (int, float)):
            # Use repr for deterministic conversion
            return repr(record).encode("utf-8")
        # Fallback: deterministic string conversion
        return str(record).encode("utf-8")

    def commit(self, records: Iterable[Any]) -> str:
        """
        Create a Merkle commitment for the given records.
        Returns the Merkle root (commitment).
        """
        self._leaves = [self._hash(self._normalize_record(r)) for r in records]
        if not self._leaves:
            raise ValueError("At least one record is required to create a commitment.")

        # Build tree levels
        level = self._leaves[:]
        self._tree = [level]

        while len(level) > 1:
            next_level = []
            for i in range(0, len(level), 2):
                left = level[i]
                right = level[i + 1] if i + 1 < len(level) else level[i]
                next_level.append(self._hash_pair(left, right))
            level = next_level
            self._tree.append(level)

        return self._tree[-1][0]

    def root(self) -> str:
        """Return the current Merkle root."""
        if not self._tree:
            raise ValueError("No commitment has been created. Call commit() first.")
        return self._tree[-1][0]

    def prove(self, index: int) -> List[Tuple[str, str]]:
        """
        Generate a Merkle proof for the record at the given index.

        Returns a list of tuples: (sibling_hash, position)
        where position is either 'left' or 'right' indicating the sibling's
        position relative to the current node.
        """
        if not self._tree:
            raise ValueError("No commitment has been created. Call commit() first.")
        if index < 0 or index >= len(self._leaves):
            raise IndexError("Record index out of range.")

        proof: List[Tuple[str, str]] = []
        idx = index
        for level in self._tree[:-1]:
            if idx % 2 == 0:
                # Right sibling
                sibling_idx = idx + 1 if idx + 1 < len(level) else idx
                proof.append((level[sibling_idx], "right"))
            else:
                # Left sibling
                sibling_idx = idx - 1
                proof.append((level[sibling_idx], "left"))
            idx //= 2
        return proof

    @classmethod
    def verify_proof(
        cls,
        record: Any,
        proof: List[Tuple[str, str]],
        root: str,
    ) -> bool:
        """
        Verify a Merkle proof for a given record and root.

        The verifier only needs the record, proof path, and expected root.
        """
        current_hash = cls._hash(cls._normalize_record(record))
        for sibling_hash, position in proof:
            if position == "right":
                current_hash = cls._hash_pair(current_hash, sibling_hash)
            elif position == "left":
                current_hash = cls._hash_pair(sibling_hash, current_hash)
            else:
                return False
        return current_hash == root

    def export_commitment(self) -> Dict[str, Any]:
        """
        Export commitment metadata for audit trails.
        This avoids exposing raw records while allowing integrity checks.
        """
        if not self._tree:
            raise ValueError("No commitment has been created. Call commit() first.")
        return {
            "root": self._tree[-1][0],
            "leaves_count": len(self._leaves),
            "hash": "sha256",
        }


__all__ = ["ZKPVerify"]
