# -*- coding: utf-8 -*-
"""
Pytest configuration and fixtures for test suite.
"""
import sys
from pathlib import Path

# Add parent directory to path so tests can import app modules
BASE = Path(__file__).resolve().parent.parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))


def pytest_configure(config):
    """Called after command line options have been parsed."""
    config.addinivalue_line(
        "markers", "unit: Unit tests for individual functions"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests combining multiple modules"
    )
    config.addinivalue_line(
        "markers", "slow: Tests that take longer to run"
    )
    config.addinivalue_line(
        "markers", "edge_case: Edge case and boundary condition tests"
    )
