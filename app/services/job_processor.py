
from datetime import datetime

from app.database import SessionLocal
from app.models import GenerationJob, RecipientCertificate
from app.services.certificate_generator import generate_certificate


def process_generation_job(job_id: str) -> None:
    db = SessionLocal()

    try:
        job = (
            db.query(GenerationJob)
            .filter(GenerationJob.id == job_id)
            .first()
        )

        if job is None:
            return

        job.status = "processing"
        db.commit()

        # Invalid recipients are already marked failed.
        # Only process recipients that passed validation.
        recipient_ids = [
            recipient.id
            for recipient in (
                db.query(RecipientCertificate)
                .filter(
                    RecipientCertificate.job_id == job_id,
                    RecipientCertificate.status == "pending",
                )
                .order_by(RecipientCertificate.id)
                .all()
            )
        ]

        for recipient_id in recipient_ids:
            recipient = (
                db.query(RecipientCertificate)
                .filter(RecipientCertificate.id == recipient_id)
                .first()
            )

            if recipient is None:
                continue

            try:
                recipient.status = "processing"
                db.commit()

                relative_path = generate_certificate(
                    name=recipient.name,
                    certificate_title=job.certificate_title,
                    organization=job.organization,
                    issue_date=job.issue_date,
                    job_id=job.id,
                    recipient_id=recipient.id,
                )

                recipient.file_path = relative_path
                recipient.status = "completed"
                recipient.error_message = None

            except Exception as exc:
                # Record the failure and continue with the next recipient.
                recipient.status = "failed"
                recipient.file_path = None
                recipient.error_message = (
                    f"Certificate generation failed: "
                    f"{type(exc).__name__}: {exc}"
                )

            finally:
                db.commit()

        # Calculate final counts from the recipient records.
        successful_count = (
            db.query(RecipientCertificate)
            .filter(
                RecipientCertificate.job_id == job_id,
                RecipientCertificate.status == "completed",
            )
            .count()
        )

        failed_count = (
            db.query(RecipientCertificate)
            .filter(
                RecipientCertificate.job_id == job_id,
                RecipientCertificate.status == "failed",
            )
            .count()
        )

        job.successful_count = successful_count
        job.failed_count = failed_count

        if successful_count == job.total_recipients:
            job.status = "completed"
        elif successful_count > 0:
            job.status = "completed_with_errors"
        else:
            job.status = "failed"

        job.completed_at = datetime.utcnow()
        db.commit()

    finally:
        db.close()
