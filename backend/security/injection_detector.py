"""
Three-layer prompt injection detection.

Layer 1 — Pattern matching: known injection phrases from constitutional_policies.
Layer 2 — Entropy analysis: high-entropy text may be obfuscated attacks.
Layer 3 — Structural heuristics: bracket overloading and abnormally long tokens.

A CRITICAL flag from any layer causes action=BLOCK — the pipeline halts before
any LLM sees the input. Security violations are never retried; the pipeline
returns a security halt record immediately.
"""

import re
from collections import Counter
from math import log2

from config.constitutional_policies import INJECTION_PATTERNS


class InjectionDetector:

    def check_input(self, text: str) -> dict:
        """
        Run all three detection layers and return a unified result.

        Returns:
            is_safe: False if action is BLOCK
            flags:   list of flag dicts from all layers
            action:  ALLOW | FLAG | BLOCK
        """
        flags: list[dict] = []
        flags.extend(self._check_patterns(text))
        entropy_flag = self._check_entropy(text)
        if entropy_flag:
            flags.append(entropy_flag)
        flags.extend(self._check_structure(text))

        has_critical = any(f["severity"] == "CRITICAL" for f in flags)
        warning_count = sum(1 for f in flags if f["severity"] == "WARNING")

        if has_critical:
            action = "BLOCK"
        elif warning_count >= 2:
            action = "FLAG"
        else:
            action = "ALLOW"

        return {
            "is_safe": action != "BLOCK",
            "flags": flags,
            "action": action,
        }

    # ------------------------------------------------------------------
    # Layer 1 — Known injection patterns
    # ------------------------------------------------------------------

    def _check_patterns(self, text: str) -> list[dict]:
        """
        Compare lowercased input against every entry in INJECTION_PATTERNS.
        Any match is CRITICAL — pipeline halts immediately, no retry.
        """
        lower = text.lower()
        flags = []
        for pattern in INJECTION_PATTERNS:
            if pattern in lower:
                flags.append({
                    "layer": "pattern_match",
                    "severity": "CRITICAL",
                    "description": f"Injection pattern detected: '{pattern}'",
                    "matched_pattern": pattern,
                })
        return flags

    # ------------------------------------------------------------------
    # Layer 2 — Shannon entropy
    # ------------------------------------------------------------------

    def _check_entropy(self, text: str) -> dict | None:
        """
        High Shannon entropy suggests obfuscated or encoded attack payloads.
        Natural language sits around 3.5–4.2 bits/char; above 4.5 is suspicious.
        """
        if not text:
            return None
        length = len(text)
        counts = Counter(text).values()
        entropy = -sum((c / length) * log2(c / length) for c in counts)
        if entropy > 4.5:
            return {
                "layer": "entropy_analysis",
                "severity": "WARNING",
                "description": f"High input entropy ({entropy:.2f} bits/char > 4.5 threshold)",
                "entropy_value": round(entropy, 4),
            }
        return None

    # ------------------------------------------------------------------
    # Layer 3 — Structural heuristics
    # ------------------------------------------------------------------

    def _check_structure(self, text: str) -> list[dict]:
        """
        Bracket overloading and abnormally long tokens are common in
        template-injection and XML-injection attempts.
        """
        flags = []
        bracket_count = text.count("[") + text.count("]")
        if bracket_count > 5:
            flags.append({
                "layer": "structural_check",
                "severity": "WARNING",
                "description": f"Excessive square brackets ({bracket_count} found, threshold 5)",
                "bracket_count": bracket_count,
            })

        words = re.split(r'\s+', text)
        long_words = [w for w in words if len(w) > 50]
        if long_words:
            flags.append({
                "layer": "structural_check",
                "severity": "WARNING",
                "description": f"Abnormally long token(s) detected (max length {max(len(w) for w in long_words)})",
                "long_token_count": len(long_words),
            })

        return flags

    # ------------------------------------------------------------------
    # Spotlighting
    # ------------------------------------------------------------------

    def spotlight_input(self, user_input: str) -> str:
        """
        Wrap user-controlled input in XML-like tags to signal zero-trust
        boundary to the LLM. Part of the sandwich defence in build_secure_prompt.
        """
        return f"<untrusted_data>{user_input}</untrusted_data>"
