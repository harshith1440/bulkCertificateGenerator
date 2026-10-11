from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    Integer,
    Date,
    DateTime,
    ForeignKey,
    Text,
)
from sqlalchemy.orm import relationship

from app.database import Base


class GenerationJob(Base):
    __tablename__ = "generation_jobs"

    id = Column(String(36), primary_key=True, index=True)

    certificate_title = Column(String(200), nullable=False)
    organization = Column(String(200), nullable=False)
    issue_date = Column(Date, nullable=False)

    status = Column(String(30), default="queued", nullable=False)

    total_recipients = Column(Integer, default=0, nullable=False)
    successful_count = Column(Integer, default=0, nullable=False)
    failed_count = Column(Integer, default=0, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    recipients = relationship(
        "RecipientCertificate",
        back_populates="job",
        cascade="all, delete-orphan",
    )


class RecipientCertificate(Base):
    __tablename__ = "recipient_certificates"

    id = Column(Integer, primary_key=True, index=True)

    job_id = Column(
        String(36),
        ForeignKey("generation_jobs.id"),
        nullable=False,
    )

    name = Column(String(150), nullable=True)
    email = Column(String(320), nullable=True)

    # Preserve the original input for validation and error reporting.
    input_data = Column(Text, nullable=False)

    status = Column(String(20), default="pending", nullable=False)

    file_path = Column(String(500), nullable=True)
    error_message = Column(Text, nullable=True)

    job = relationship("GenerationJob", back_populates="recipients")