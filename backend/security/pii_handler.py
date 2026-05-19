"""
Regex-based PII detection and tokenization.

Zero external dependencies — no Presidio, no spaCy. Reliable and deployable
anywhere Python runs. The detect_and_tokenize / mask_for_output split is
intentional: LLM agents only ever see tokens, never real PII values.
token_map stays at the pipeline boundary and is never passed to any LLM agent.

In production this could be extended with Microsoft Presidio or an enterprise
DLP service for contextual detection (e.g. names, addresses). The interface
here is compatible with that upgrade — callers use detect_and_tokenize and
mask_for_output regardless of the underlying engine.
"""

import re
from collections import Counter


class PIIHandler:
    # Patterns ordered from most-specific to least-specific so that card
    # numbers (16 digits) are matched before the shorter ACCOUNT_NUMBER
    # pattern can consume them.
    PATTERNS: dict[str, str] = {
        "CARD_NUMBER":    r'\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b',
        "EMAIL":          r'\b[\w.+\-]+@[\w\-]+\.[\w.]+\b',
        "PHONE":          r'\b(\+\d{1,3}[\s.\-])?\(?\d{3}\)?[\s.\-]\d{3}[\s.\-]\d{4,6}\b',
        "SSN":            r'\b\d{3}-\d{2}-\d{4}\b',
        "ACCOUNT_NUMBER": r'\b\d{8,12}\b',
        "API_KEY":        r'\b[A-Za-z0-9]{32,45}\b',
    }

    def detect_and_tokenize(self, text: str) -> tuple[str, dict]:
        """
        Find all PII in text, replace each with a unique token, return both.

        Matches are processed in reverse position order so that replacing a
        match does not shift the string positions of earlier (higher-index)
        matches still waiting to be processed.

        Returns:
            tokenized_text: original text with PII replaced by tokens
            token_map:      {token: real_value} — NEVER pass this to an LLM agent
        """
        token_map: dict[str, str] = {}
        # Collect (start, end, pii_type, matched_text) across all patterns
        all_matches: list[tuple[int, int, str, str]] = []

        for pii_type, pattern in self.PATTERNS.items():
            for m in re.finditer(pattern, text):
                all_matches.append((m.start(), m.end(), pii_type, m.group()))

        # Remove overlapping matches: keep the one that starts earlier;
        # if same start, keep the longer one.
        all_matches.sort(key=lambda x: (x[0], -(x[1] - x[0])))
        non_overlapping: list[tuple[int, int, str, str]] = []
        last_end = -1
        for start, end, pii_type, value in all_matches:
            if start >= last_end:
                non_overlapping.append((start, end, pii_type, value))
                last_end = end

        # Assign tokens and build token_map
        type_counters: dict[str, int] = Counter()
        match_to_token: list[tuple[int, int, str]] = []
        for start, end, pii_type, value in non_overlapping:
            type_counters[pii_type] += 1
            token = f"[{pii_type}_TOKEN_{type_counters[pii_type]:03d}]"
            token_map[token] = value
            match_to_token.append((start, end, token))

        # Replace in reverse order to preserve earlier positions
        tokenized = text
        for start, end, token in sorted(match_to_token, key=lambda x: x[0], reverse=True):
            tokenized = tokenized[:start] + token + tokenized[end:]

        return tokenized, token_map

    def mask_for_output(self, text: str, token_map: dict) -> str:
        """
        Replace tokens with partially-masked real values for analyst reports.

        Masking rules (show enough to identify the record, hide the secret):
          CARD_NUMBER    → first 4 and last 4 digits: 4532-****-****-9012
          EMAIL          → first 2 chars + domain:    jo***@email.com
          PHONE          → last 4 digits only:         ***-***-1234
          Others         → first 2 + last 2:           ac****12
        """
        result = text
        for token, real_value in token_map.items():
            masked = self._mask_value(token, real_value)
            result = result.replace(token, masked)
        return result

    def _mask_value(self, token: str, real_value: str) -> str:
        if "CARD_NUMBER" in token:
            digits = re.sub(r'[\s\-]', '', real_value)
            if len(digits) >= 8:
                return f"{digits[:4]}-****-****-{digits[-4:]}"
            return "****-****-****-****"

        if "EMAIL" in token:
            at = real_value.find("@")
            if at >= 2:
                return real_value[:2] + "***" + real_value[at:]
            return "***" + real_value[at:] if at >= 0 else "***@***.***"

        if "PHONE" in token:
            digits = re.sub(r'\D', '', real_value)
            if len(digits) >= 4:
                return f"***-***-{digits[-4:]}"
            return "***-***-****"

        # SSN, ACCOUNT_NUMBER, API_KEY, and anything else
        if len(real_value) >= 4:
            return real_value[:2] + "****" + real_value[-2:]
        return "****"

    def scan_for_pii_in_output(self, text: str) -> list[str]:
        """
        Scan text for unmasked PII and return the types found (not the values).

        Used by the Guardrail Agent's post-agent check. Returning types only —
        never the matched values — ensures this method itself cannot leak PII
        into logs or flag records.
        """
        found_types: list[str] = []
        for pii_type, pattern in self.PATTERNS.items():
            if re.search(pattern, text):
                found_types.append(pii_type)
        return found_types
