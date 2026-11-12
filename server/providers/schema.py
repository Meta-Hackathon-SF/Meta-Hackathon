"""Minimal JSON Schema subset validator.

The same schema dict is sent to the provider as ``response_format.json_schema``
and checked locally, because provider-side structured output is not a security
boundary. Supported keywords: type, properties, required, additionalProperties
(false only), items, enum, minItems, maxItems, minLength, maxLength, minimum,
maximum. Unsupported keywords raise at registration time so schemas cannot
silently drift into keywords that are not enforced here.
"""
from __future__ import annotations

from typing import Any

SUPPORTED = frozenset({
    "type", "properties", "required", "additionalProperties", "items", "enum",
    "minItems", "maxItems", "minLength", "maxLength", "minimum", "maximum",
    "description",
})

_TYPES = {
    "object": dict,
    "array": list,
    "string": str,
    "boolean": bool,
    "null": type(None),
}


class SchemaViolation(ValueError):
    def __init__(self, path: str, message: str) -> None:
        super().__init__(f"{path or '$'}: {message}")
        self.path = path or "$"


def check_schema_supported(schema: dict[str, Any], path: str = "$") -> None:
    unknown = set(schema) - SUPPORTED
    if unknown:
        raise ValueError(f"unsupported schema keywords at {path}: {sorted(unknown)}")
    if schema.get("type") == "object" or "properties" in schema:
        if schema.get("additionalProperties", None) is not False:
            raise ValueError(f"object schema at {path} must set additionalProperties: false")
        for name, sub in schema.get("properties", {}).items():
            check_schema_supported(sub, f"{path}.{name}")
    if "items" in schema:
        check_schema_supported(schema["items"], f"{path}[]")


def _type_ok(value: Any, t: str) -> bool:
    if t == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if t == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    py = _TYPES.get(t)
    if py is None:
        raise ValueError(f"unknown type {t}")
    if py is dict or py is list or py is str:
        return isinstance(value, py)
    return isinstance(value, py)


def validate(value: Any, schema: dict[str, Any], path: str = "") -> None:
    """Raise SchemaViolation on the first mismatch."""
    t = schema.get("type")
    if t is not None:
        types = t if isinstance(t, list) else [t]
        if not any(_type_ok(value, x) for x in types):
            raise SchemaViolation(path, f"expected {t}")
    if "enum" in schema and value not in schema["enum"]:
        raise SchemaViolation(path, "value not in enum")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            raise SchemaViolation(path, "string too short")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            raise SchemaViolation(path, "string too long")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            raise SchemaViolation(path, "below minimum")
        if "maximum" in schema and value > schema["maximum"]:
            raise SchemaViolation(path, "above maximum")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            raise SchemaViolation(path, "too few items")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            raise SchemaViolation(path, "too many items")
        if "items" in schema:
            for i, item in enumerate(value):
                validate(item, schema["items"], f"{path}[{i}]")
    if isinstance(value, dict) and ("properties" in schema or schema.get("type") == "object"):
        props: dict[str, Any] = schema.get("properties", {})
        for key in value:
            if key not in props:
                raise SchemaViolation(f"{path}.{key}", "unexpected property")
        for key in schema.get("required", []):
            if key not in value:
                raise SchemaViolation(f"{path}.{key}", "required property missing")
        for key, sub in props.items():
            if key in value:
                validate(value[key], sub, f"{path}.{key}")
