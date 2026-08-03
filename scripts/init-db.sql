"""
Database initialization script for Docker.
"""
-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- The tables will be created by Alembic/SQLAlchemy
-- This file can be used for initial data or extensions