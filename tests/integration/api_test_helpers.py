"""Helper asersi untuk pengujian API (status, header, JSON Schema)."""

from __future__ import annotations

from typing import Any, Mapping, Optional

from jsonschema import validate


def assert_json_content_type(response: Any) -> None:
    ct = response.headers.get("Content-Type", "")
    assert "application/json" in ct.lower(), (
        f"Content-Type harus application/json, dapat: {ct!r}"
    )


def validate_instance(instance: Any, schema: Mapping[str, Any]) -> None:
    """Validasi instance terhadap JSON Schema; raise jsonschema.ValidationError jika gagal."""
    validate(instance=instance, schema=schema)


def assert_api_json(
    response: Any,
    expected_status: int,
    schema: Optional[Mapping[str, Any]] = None,
    *,
    check_json_content_type: bool = True,
) -> Any:
    """
    Asersi status HTTP, opsional Content-Type JSON, parse JSON, opsional validasi schema.
    Mengembalikan dict/list hasil get_json().
    """
    assert response.status_code == expected_status, (
        f"status {response.status_code} != {expected_status}, body: {response.get_data(as_text=True)[:500]}"
    )
    if check_json_content_type:
        assert_json_content_type(response)
    data = response.get_json()
    assert data is not None, "body bukan JSON valid"
    if schema is not None:
        validate_instance(data, schema)
    return data
