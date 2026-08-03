"""API router initialization."""

from app.api import auth, aws, health, items, users

__all__ = [
    "auth",
    "users",
    "items",
    "aws",
    "health",
]
