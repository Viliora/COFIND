"""Hook pytest global untuk folder tes."""

from __future__ import annotations

import pytest


def pytest_collection_modifyitems(config, items):
    root = config.rootpath / "tests" / "integration"
    try:
        root_resolved = root.resolve()
    except OSError:
        return
    for item in items:
        try:
            p = item.path.resolve()
        except (OSError, AttributeError):
            continue
        if root_resolved in p.parents or p.parent == root_resolved:
            item.add_marker(pytest.mark.integration)
