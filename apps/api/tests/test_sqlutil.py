import pytest

from app.sqlutil import PATCHABLE_COLUMNS, patch_sets


def test_builds_numbered_sets() -> None:
    sets, values = patch_sets("projects", {"name": "x", "archived": True})
    assert sets == "name = $2, archived = $3"
    assert values == ["x", True]


def test_id_param_offset() -> None:
    sets, _ = patch_sets("proj_tasks", {"title": "x"}, id_param=2)
    assert sets == "title = $3"


def test_unknown_column_refused() -> None:
    with pytest.raises(ValueError, match="refusing to interpolate"):
        patch_sets("projects", {"name": "x", "tenant_id": "sneaky"})


def test_unknown_table_refused() -> None:
    # `tenants` became patchable with the operator console's edit endpoint, so
    # this uses audit_log — append-only by design and never a PATCH target.
    with pytest.raises(KeyError):
        patch_sets("audit_log", {"action": "x"})


def test_allowlists_contain_no_sql_metacharacters() -> None:
    for table, cols in PATCHABLE_COLUMNS.items():
        for col in cols:
            assert col.replace("_", "").isalnum(), f"{table}.{col}"
