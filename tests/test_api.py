import io
import zipfile

import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine, SessionLocal
from app.main import app, ARCHIVE_DIR, PROJECT_ROOT
from app.models import GenerationJob, RecipientCertificate
import app.services.job_processor as job_processor


@pytest.fixture
def client():
    Base.metadata.create_all(bind=engine)

    # Preserve jobs that existed before the test.
    with SessionLocal() as db:
        existing_job_ids = {
            row[0] for row in db.query(GenerationJob.id).all()
        }

    with TestClient(app) as test_client:
        yield test_client

    # Remove jobs and files created by this test.
    with SessionLocal() as db:
        jobs = db.query(GenerationJob).all()

        for job in jobs:
            if job.id in existing_job_ids:
                continue

            for recipient in job.recipients:
                if recipient.file_path:
                    file_path = (
                        PROJECT_ROOT / recipient.file_path
                    ).resolve()
                    file_path.unlink(missing_ok=True)

            (ARCHIVE_DIR / f"{job.id}.zip").unlink(
                missing_ok=True
            )
            db.delete(job)

        db.commit()


def make_payload(recipients):
    return {
        "certificate_title": "Python Workshop",
        "organization": "ABC Learning Center",
        "issue_date": "2026-10-11",
        "recipients": recipients,
    }


def submit_job(client, recipients):
    response = client.post(
        "/api/v1/certificate-jobs",
        json=make_payload(recipients),
    )
    assert response.status_code == 202
    return response.json()


def get_job_status(client, job_id):
    response = client.get(
        f"/api/v1/certificate-jobs/{job_id}"
    )
    assert response.status_code == 200
    return response.json()


def test_create_generation_job(client):
    result = submit_job(
        client,
        [{"name": "Test User", "email": "test@example.com"}],
    )

    assert result["job_id"]
    assert result["total_recipients"] == 1
    assert result["valid_recipients"] == 1
    assert result["invalid_recipients"] == 0

    job = get_job_status(client, result["job_id"])
    assert job["status"] == "completed"
    assert job["successful_count"] == 1


def test_rejects_missing_required_job_fields(client):
    response = client.post(
        "/api/v1/certificate-jobs",
        json={
            "certificate_title": "Python Workshop",
            "issue_date": "2026-10-11",
            "recipients": [
                {
                    "name": "Test User",
                    "email": "test@example.com",
                }
            ],
        },
    )

    assert response.status_code == 422


def test_invalid_recipient_does_not_stop_valid_recipient(client):
    result = submit_job(
        client,
        [
            {"name": "Valid User", "email": "valid@example.com"},
            {"name": "Invalid User", "email": "not-an-email"},
        ],
    )

    job = get_job_status(client, result["job_id"])

    assert job["status"] == "completed_with_errors"
    assert job["successful_count"] == 1
    assert job["failed_count"] == 1

    failed_recipient = next(
        r for r in job["recipients"]
        if r["name"] == "Invalid User"
    )
    assert failed_recipient["status"] == "failed"
    assert "email" in failed_recipient["error_message"]


def test_certificate_generation_creates_pdf(client):
    result = submit_job(
        client,
        [{"name": "PDF Test User", "email": "pdf@example.com"}],
    )

    with SessionLocal() as db:
        recipient = (
            db.query(RecipientCertificate)
            .filter(
                RecipientCertificate.job_id == result["job_id"]
            )
            .first()
        )

        assert recipient is not None
        assert recipient.status == "completed"
        assert recipient.file_path is not None

        pdf_path = PROJECT_ROOT / recipient.file_path

        assert pdf_path.is_file()
        assert pdf_path.read_bytes().startswith(b"%PDF-")


def test_job_progress_is_correct(client):
    result = submit_job(
        client,
        [
            {"name": "User One", "email": "one@example.com"},
            {"name": "User Two", "email": "two@example.com"},
            {"name": "User Three", "email": "three@example.com"},
        ],
    )

    job = get_job_status(client, result["job_id"])

    assert job["total_recipients"] == 3
    assert job["successful_count"] == 3
    assert job["failed_count"] == 0
    assert job["pending_or_processing_count"] == 0
    assert job["progress_percent"] == 100
    assert job["status"] == "completed"


def test_one_generation_failure_does_not_stop_others(
    client, monkeypatch
):
    original_generator = job_processor.generate_certificate

    def failing_generator(**kwargs):
        if kwargs["name"] == "Failure Participant":
            raise RuntimeError("Simulated PDF failure")

        return original_generator(**kwargs)

    monkeypatch.setattr(
        job_processor,
        "generate_certificate",
        failing_generator,
    )

    result = submit_job(
        client,
        [
            {
                "name": "Success Participant",
                "email": "success@example.com",
            },
            {
                "name": "Failure Participant",
                "email": "failure@example.com",
            },
        ],
    )

    job = get_job_status(client, result["job_id"])

    assert job["status"] == "completed_with_errors"
    assert job["successful_count"] == 1
    assert job["failed_count"] == 1

    failed = next(
        r for r in job["recipients"]
        if r["name"] == "Failure Participant"
    )

    assert failed["status"] == "failed"
    assert "Simulated PDF failure" in failed["error_message"]


def test_download_pdf_and_zip(client):
    result = submit_job(
        client,
        [
            {"name": "Download One", "email": "one@example.com"},
            {"name": "Download Two", "email": "two@example.com"},
        ],
    )

    job = get_job_status(client, result["job_id"])
    job_id = result["job_id"]

    first_recipient = job["recipients"][0]
    recipient_id = first_recipient["recipient_id"]

    # Test individual PDF download.
    pdf_response = client.get(
        f"/api/v1/certificate-jobs/{job_id}/recipients/"
        f"{recipient_id}/certificate"
    )

    assert pdf_response.status_code == 200
    assert pdf_response.content.startswith(b"%PDF-")

    # Test ZIP download.
    zip_response = client.get(
        f"/api/v1/certificate-jobs/{job_id}/download"
    )

    assert zip_response.status_code == 200
    assert zip_response.headers["content-type"] == "application/zip"

    with zipfile.ZipFile(
        io.BytesIO(zip_response.content)
    ) as archive:
        pdf_names = [
            name for name in archive.namelist()
            if name.endswith(".pdf")
        ]

        assert len(pdf_names) == 2
        