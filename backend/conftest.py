import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "llm: marks tests requiring LLM API access (deselect with -m 'not llm')",
    )
