import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    HTTPException,
    status,
)
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app import models
from app.database import Base, engine, get_db
from app.models import GenerationJob, RecipientCertificate
from app.schemas import CertificateJobCreate, RecipientInput
from app.services.job_processor import process_generation_job


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Bulk Certificate Generator",
    description="Generate and track certificates for multiple recipients.",
    version="1.0.0",
    lifespan=lifespan,
)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

CERTIFICATE_DIR = (
    PROJECT_ROOT / "storage" / "certificates"
).resolve()

ARCHIVE_DIR = (
    PROJECT_ROOT / "storage" / "archives"
).resolve()


def resolve_certificate_file(relative_path: str | None) -> Path:
    if not relative_path:
        raise HTTPException(
            status_code=404,
            detail="Certificate file not found",
        )

    file_path = (PROJECT_ROOT / relative_path).resolve()

    # Ensure the requested file is inside certificate storage.
    try:
        file_path.relative_to(CERTIFICATE_DIR)
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail="Certificate file not found",
        )

    if not file_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Generated certificate file does not exist",
        )

    return file_path

@app.get("/")
def root():
    return {
        "message": "Bulk Certificate Generator API is running"
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.post(
    "/api/v1/certificate-jobs",
    status_code=status.HTTP_202_ACCEPTED,
)
def create_certificate_job(
    payload: CertificateJobCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    job_id = str(uuid4())

    job = GenerationJob(
        id=job_id,
        certificate_title=payload.certificate_title,
        organization=payload.organization,
        issue_date=payload.issue_date,
        status="queued",
        total_recipients=len(payload.recipients),
        successful_count=0,
        failed_count=0,
    )

    db.add(job)

    recipient_records = []
    invalid_count = 0

    for raw_recipient in payload.recipients:
        # Preserve any supplied name/email for error reporting.
        raw_name = (
            raw_recipient.get("name")
            if isinstance(raw_recipient, dict)
            else None
        )
        raw_email = (
            raw_recipient.get("email")
            if isinstance(raw_recipient, dict)
            else None
        )

        try:
            recipient = RecipientInput.model_validate(raw_recipient)

            record = RecipientCertificate(
                job_id=job_id,
                name=recipient.name,
                email=str(recipient.email),
                input_data=json.dumps(
                    recipient.model_dump(mode="json")
                ),
                status="pending",
            )

        except ValidationError as exc:
            invalid_count += 1

            messages = [
                f"{'.'.join(str(part) for part in error['loc'])}: "
                f"{error['msg']}"
                for error in exc.errors()
            ]

            record = RecipientCertificate(
                job_id=job_id,
                name=raw_name if isinstance(raw_name, str) else None,
                email=raw_email if isinstance(raw_email, str) else None,
                input_data=json.dumps(raw_recipient, default=str),
                status="failed",
                error_message="Invalid recipient data: "
                + "; ".join(messages),
            )

        recipient_records.append(record)

    job.failed_count = invalid_count

    db.add_all(recipient_records)
    db.commit()

    # Schedule processing after the job is saved.
    background_tasks.add_task(process_generation_job, job_id)

    return {
        "job_id": job_id,
        "status": "queued",
        "total_recipients": len(payload.recipients),
        "valid_recipients": len(payload.recipients) - invalid_count,
        "invalid_recipients": invalid_count,
        "status_url": f"/api/v1/certificate-jobs/{job_id}",
    }


@app.get("/api/v1/certificate-jobs/{job_id}")
def get_certificate_job(
    job_id: str,
    db: Session = Depends(get_db),
):
    job = (
        db.query(GenerationJob)
        .filter(GenerationJob.id == job_id)
        .first()
    )

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Certificate generation job not found",
        )

    recipients = (
        db.query(RecipientCertificate)
        .filter(RecipientCertificate.job_id == job_id)
        .order_by(RecipientCertificate.id)
        .all()
    )

    completed = sum(r.status == "completed" for r in recipients)
    failed = sum(r.status == "failed" for r in recipients)
    processed = completed + failed

    return {
        "job_id": job.id,
        "certificate_title": job.certificate_title,
        "organization": job.organization,
        "status": job.status,
        "total_recipients": job.total_recipients,
        "successful_count": completed,
        "failed_count": failed,
        "pending_or_processing_count": job.total_recipients - processed,
        "progress_percent": round(
            processed / job.total_recipients * 100, 2
        ) if job.total_recipients else 100,
        "created_at": job.created_at,
        "completed_at": job.completed_at,
        "recipients": [
            {
                "recipient_id": r.id,
                "name": r.name,
                "email": r.email,
                "status": r.status,
                "error_message": r.error_message,
            }
            for r in recipients
        ],
    }

@app.get(
    "/api/v1/certificate-jobs/{job_id}/recipients/"
    "{recipient_id}/certificate"
)
def download_certificate(
    job_id: str,
    recipient_id: int,
    db: Session = Depends(get_db),
):
    recipient = (
        db.query(RecipientCertificate)
        .filter(
            RecipientCertificate.job_id == job_id,
            RecipientCertificate.id == recipient_id,
        )
        .first()
    )

    if recipient is None:
        raise HTTPException(
            status_code=404,
            detail="Recipient not found for this job",
        )

    if recipient.status != "completed":
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Certificate is not available",
                "status": recipient.status,
                "error": recipient.error_message,
            },
        )

    file_path = resolve_certificate_file(recipient.file_path)

    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename=f"certificate_{recipient.id}.pdf",
    )

@app.get("/api/v1/certificate-jobs/{job_id}/download")
def download_job_certificates(
    job_id: str,
    db: Session = Depends(get_db),
):
    job = (
        db.query(GenerationJob)
        .filter(GenerationJob.id == job_id)
        .first()
    )

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Certificate generation job not found",
        )

    if job.status in {"queued", "processing"}:
        raise HTTPException(
            status_code=409,
            detail="Job is still processing. Check its status and retry.",
        )

    recipients = (
        db.query(RecipientCertificate)
        .filter(
            RecipientCertificate.job_id == job_id,
            RecipientCertificate.status == "completed",
        )
        .order_by(RecipientCertificate.id)
        .all()
    )

    if not recipients:
        raise HTTPException(
            status_code=409,
            detail="This job has no successfully generated certificates.",
        )

    available_files = [
        (recipient, resolve_certificate_file(recipient.file_path))
        for recipient in recipients
    ]

    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    archive_path = ARCHIVE_DIR / f"{job_id}.zip"

    with ZipFile(
        archive_path,
        mode="w",
        compression=ZIP_DEFLATED,
    ) as archive:
        for recipient, file_path in available_files:
            archive.write(
                file_path,
                arcname=f"certificate_{recipient.id}.pdf",
            )

    return FileResponse(
        path=archive_path,
        media_type="application/zip",
        filename=f"certificates_{job_id}.zip",
    )