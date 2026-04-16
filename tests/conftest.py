"""
Shared pytest fixtures and configuration.
Sets RESUME_LINK env var for all tests so templates don't need patching everywhere.
"""
import os
import pytest


@pytest.fixture(autouse=True)
def set_default_env(monkeypatch):
    monkeypatch.setenv("RESUME_LINK", "https://drive.google.com/test-resume")
