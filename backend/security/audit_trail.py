"""
Tamper-evident audit trail for the fraud detection pipeline.

Each pipeline result is hashed (SHA-256) at the point of recording. Any
subsequent modification to a record changes the hash, making tampering
immediately detectable.

What is logged vs what is not:
  LOGGED:   risk scores, levels, actions, agent statuses, flag counts,
            transaction reference (opaque ID only), timestamps
  NOT LOGGED: raw transaction data, PII, token_map, guardrail flag details,
              any fields that could reconstruct the original input

This is PII-aware by construction — only derived metadata reaches the log file.
"""

import hashlib
import json
import os
from datetime import datetime, timezone


class AuditTrail:

    LOG_DIR = "logs"
    LOG_FILE = "logs/audit_trail.jsonl"

    def __init__(self):
        self.records: list[dict] = []
        os.makedirs(self.LOG_DIR, exist_ok=True)

    def record_pipeline_result(
        self,
        transaction_ref: str,
        pipeline_result: dict,
        agent_statuses: dict,
        guardrail_flags: list,
        pipeline_version: str = "1.0.0",
    ) -> str:
        """
        Build a PII-safe audit record, hash it, persist it, and return the hash.

        Only whitelisted fields from pipeline_result are extracted. Any field
        not in the whitelist is silently ignored — this prevents future state
        keys from accidentally entering the audit log.

        Returns the 64-character hex SHA-256 integrity hash.
        """
        record = {
            "transaction_ref": transaction_ref,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "pipeline_version": pipeline_version,
            "agent_statuses": agent_statuses,
            # Whitelisted fields from pipeline_result only
            "final_risk_score": pipeline_result.get("final_risk_score"),
            "final_risk_level": pipeline_result.get("final_risk_level"),
            "recommended_action": pipeline_result.get("recommended_action"),
            "critic_verdict": pipeline_result.get("critic_verdict"),
            "rule_violations_count": len(
                pipeline_result.get("rule_violations", {}).get("violations", [])
            ),
            # Count only — guardrail flag details are not logged
            "guardrail_flags_count": len(guardrail_flags),
            "reliability": pipeline_result.get("reliability", "UNKNOWN"),
        }

        integrity_hash = self._hash_record(record)
        record["integrity_hash"] = integrity_hash

        self.records.append(record)
        self._append_to_log(record)

        return integrity_hash

    def verify_record_integrity(self, record: dict) -> bool:
        """
        Verify a record has not been modified since it was written.

        Removes integrity_hash, recomputes the hash from the remaining fields,
        and compares against the stored value. Returns True only on exact match.
        """
        record_copy = dict(record)
        stored_hash = record_copy.pop("integrity_hash", None)
        if stored_hash is None:
            return False
        recomputed = self._hash_record(record_copy)
        return recomputed == stored_hash

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _hash_record(record: dict) -> str:
        serialized = json.dumps(record, sort_keys=True, default=str).encode()
        return hashlib.sha256(serialized).hexdigest()

    def _append_to_log(self, record: dict) -> None:
        try:
            with open(self.LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, default=str) + "\n")
        except OSError:
            # Log write failure must not crash the pipeline — the in-memory
            # record still exists and the hash was already returned to the caller.
            pass
