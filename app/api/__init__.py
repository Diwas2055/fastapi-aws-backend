"""
API router initialization.
"""
from app.api import auth, users, items, aws, health

__all__ = [
    "auth",
    "users",
    "items",
    "aws",
    "health",
]