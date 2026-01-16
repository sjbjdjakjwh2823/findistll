"""
SQLAlchemy Models for FinDistill

Consolidated models for Vercel Serverless deployment.
Includes User, Document, and ExtractedResult with pgvector support.
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship, mapped_column
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector

from .db import Base


class User(Base):
    """User model for authentication and document ownership."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    # Note: Documents are now linked via Supabase Auth user_id (UUID string)


class Document(Base):
    """Document model for uploaded files."""
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)  # Can be empty/placeholder in serverless
    file_type = Column(String, nullable=True)  # MIME type of uploaded file
    upload_date = Column(DateTime(timezone=True), server_default=func.now())
    # Supabase Auth uses UUID strings for user IDs
    user_id = Column(String, nullable=True, index=True)

    results = relationship("ExtractedResult", back_populates="document")


class ExtractedResult(Base):
    """Extracted data from processed documents."""
    __tablename__ = "extracted_results"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"))
    data = Column(JSON, nullable=False)  # Stores refined text/table data as JSONB
    embedding = mapped_column(Vector(768), nullable=True)  # 768-dim vector for Gemini embeddings

    document = relationship("Document", back_populates="results")
