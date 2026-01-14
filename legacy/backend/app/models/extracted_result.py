from sqlalchemy import Column, Integer, ForeignKey, JSON
from sqlalchemy.orm import relationship, Mapped, mapped_column
from pgvector.sqlalchemy import Vector
from ..core.db import Base

class ExtractedResult(Base):
    __tablename__ = "extracted_results"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"))
    data = Column(JSON, nullable=False)  # Stores refined text/table data
    embedding = mapped_column(Vector(768)) # 768-dim vector for Gemini embeddings

    document = relationship("Document", backref="results")
