"""Public application configuration; never infer provider or authentication settings."""

import os
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlsplit

CONTRACT_VERSION = "2.0.0"
Environment = Literal["development", "test", "production"]


@dataclass(frozen=True)
class Settings:
    environment: Environment = "development"
    allowed_origins: tuple[str, ...] = ("http://localhost:5173", "http://127.0.0.1:5173")

    def __post_init__(self) -> None:
        if self.environment not in {"development", "test", "production"}:
            raise ValueError("Invalid CONSTELLATIONS_ENV; use development, test, or production")
        for origin in self.allowed_origins:
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.hostname in {None, "*"}
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("CONSTELLATIONS_ALLOWED_ORIGINS must contain explicit web origins")
            try:
                _ = parsed.port
            except ValueError as error:
                raise ValueError("Invalid port in CONSTELLATIONS_ALLOWED_ORIGINS") from error
        if self.environment == "production" and not self.allowed_origins:
            raise ValueError("Production requires an explicit CONSTELLATIONS_ALLOWED_ORIGINS list")

    @classmethod
    def from_env(cls) -> "Settings":
        environment = os.getenv("CONSTELLATIONS_ENV", "development")
        raw_origins = os.getenv("CONSTELLATIONS_ALLOWED_ORIGINS")
        if environment == "production" and raw_origins is None:
            raise ValueError("Production requires CONSTELLATIONS_ALLOWED_ORIGINS")
        origins = (
            cls.allowed_origins
            if raw_origins is None
            else tuple(origin.strip() for origin in raw_origins.split(",") if origin.strip())
        )
        return cls(environment=environment, allowed_origins=origins)  # type: ignore[arg-type]
