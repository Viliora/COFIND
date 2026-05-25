"""JSON Schema untuk validasi bentuk respons API (jsonschema)."""

# --- Umum ---
ERROR_BODY = {
    "type": "object",
    "required": ["status", "message"],
    "properties": {
        "status": {"type": "string", "enum": ["error"]},
        "message": {"type": "string"},
    },
    "additionalProperties": True,
}

SUCCESS_STATUS = {
    "type": "object",
    "required": ["status"],
    "properties": {"status": {"type": "string", "enum": ["success"]}},
    "additionalProperties": True,
}

# --- Root & util ---
HOME = {
    "type": "object",
    "required": ["message"],
    "properties": {"message": {"type": "string"}},
    "additionalProperties": False,
}

API_TEST = {
    "type": "object",
    "required": ["status", "message", "timestamp", "hf_client_ready", "llm_backend"],
    "properties": {
        "status": {"type": "string"},
        "message": {"type": "string"},
        "timestamp": {"type": "number"},
        "hf_client_ready": {"type": "boolean"},
        "llm_backend": {"type": "string"},
    },
    "additionalProperties": False,
}

HEALTH = {
    "type": "object",
    "required": ["status", "llm_available", "llm_backend", "rerank_backend", "summary_async_enabled"],
    "properties": {
        "status": {"type": "string"},
        "llm_available": {"type": "boolean"},
        "llm_backend": {"type": "string"},
        "rerank_backend": {"type": "string"},
        "summary_async_enabled": {"type": "boolean"},
        "redis_ok": {"type": "boolean"},
        "celery_worker_ok": {"type": "boolean"},
    },
    "additionalProperties": True,
}

# --- Auth ---
USER_CORE = {
    "type": "object",
    "required": ["id", "username", "email"],
    "properties": {
        "id": {"type": "integer"},
        "username": {"type": "string"},
        "email": {"type": "string"},
        "full_name": {"type": ["string", "null"]},
        "is_admin": {"type": "integer"},
    },
    "additionalProperties": True,
}

AUTH_SIGNUP_SUCCESS = {
    "type": "object",
    "required": ["status", "user", "token", "expires_in"],
    "properties": {
        "status": {"type": "string", "enum": ["success"]},
        "user": USER_CORE,
        "token": {"type": "string", "minLength": 8},
        "expires_in": {"type": "integer", "minimum": 1},
    },
    "additionalProperties": False,
}

AUTH_LOGIN_SUCCESS = {
    "type": "object",
    "required": ["status", "user", "token", "expires_in"],
    "properties": {
        "status": {"type": "string", "enum": ["success"]},
        "user": USER_CORE,
        "token": {"type": "string", "minLength": 8},
        "expires_in": {"type": "integer", "minimum": 1},
    },
    "additionalProperties": False,
}

AUTH_VERIFY_SUCCESS = {
    "type": "object",
    "required": ["status", "user"],
    "properties": {
        "status": {"type": "string", "enum": ["success"]},
        "user": USER_CORE,
    },
    "additionalProperties": False,
}

AUTH_USER_ME_SUCCESS = AUTH_VERIFY_SUCCESS

AUTH_LOGOUT_SUCCESS = {
    "type": "object",
    "required": ["status", "message"],
    "properties": {
        "status": {"type": "string", "enum": ["success"]},
        "message": {"type": "string"},
    },
    "additionalProperties": False,
}

AUTH_UPDATE_PROFILE_SUCCESS = {
    "type": "object",
    "required": ["status", "user"],
    "properties": {
        "status": {"type": "string", "enum": ["success"]},
        "user": {
            "type": "object",
            "required": ["id", "username", "email"],
            "properties": {
                "id": {"type": "integer"},
                "username": {"type": "string"},
                "email": {"type": "string"},
                "is_admin": {"type": "integer"},
                "full_name": {"type": ["string", "null"]},
                "avatar_url": {"type": ["string", "null"]},
                "bio": {"type": ["string", "null"]},
                "phone": {"type": ["string", "null"]},
            },
            "additionalProperties": True,
        },
    },
    "additionalProperties": False,
}

# --- Coffee shops ---
COFFEESHOPS_LIST = {
    "type": "object",
    "required": ["status", "data", "total"],
    "properties": {
        "status": {"type": "string", "enum": ["success"]},
        "data": {
            "type": "array",
            "items": {"type": "object", "additionalProperties": True},
        },
        "total": {"type": "integer", "minimum": 0},
    },
    "additionalProperties": False,
}
