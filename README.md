# Bulk Certificate Generator

A FastAPI backend that generates PDF certificates in bulk, tracks job progress, handles individual recipient failures, and provides PDF and ZIP downloads.

## Features

- Submit one request for multiple recipients.
- Validate recipient names and email addresses.
- Generate PDF certificates using a predefined template.
- Track job and individual recipient statuses.
- Continue processing when an individual certificate fails.
- Download individual certificates or a ZIP of successful certificates.
- Store job and recipient information in a relational database.
- Test the API using automated pytest tests.

## Technology Stack

- **Python** — application logic
- **FastAPI** — REST API
- **SQLite** — relational database
- **SQLAlchemy** — database ORM
- **ReportLab** — PDF generation
- **Pydantic** — input validation
- **pytest** — automated testing

## Project Structure

```text
bulk-certificate-generator/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   └── services/
│       ├── __init__.py
│       ├── certificate_generator.py
│       └── job_processor.py
├── storage/
│   ├── certificates/
│   └── archives/
├── tests/
│   └── test_api.py
├── requirements.txt
├── .gitignore
└── README.md
```

## Prerequisites

- Python 3.10 or later
- pip

## Setup

Clone the repository or navigate to the project directory.

Create a virtual environment:

```bash
python3 -m venv .venv
```

Activate it on macOS or Linux:

```bash
source .venv/bin/activate
```

Install the dependencies:

```bash
python3 -m pip install -r requirements.txt
```

## Run the Application

Start the FastAPI development server:

```bash
uvicorn app.main:app --reload
```

The API runs at:

`http://127.0.0.1:8000`

Interactive API documentation is available at:

`http://127.0.0.1:8000/docs`

Health check:

`http://127.0.0.1:8000/health`

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | API homepage |
| GET | `/health` | Health check |
| POST | `/api/v1/certificate-jobs` | Create a bulk generation job |
| GET | `/api/v1/certificate-jobs/{job_id}` | Retrieve job status and recipient results |
| GET | `/api/v1/certificate-jobs/{job_id}/recipients/{recipient_id}/certificate` | Download an individual PDF |
| GET | `/api/v1/certificate-jobs/{job_id}/download` | Download successful certificates as a ZIP |

## Submit a Bulk Generation Request

Send a POST request to:

`http://127.0.0.1:8000/api/v1/certificate-jobs`

Example using curl:

```bash
curl -X POST \
  "http://127.0.0.1:8000/api/v1/certificate-jobs" \
  -H "Content-Type: application/json" \
  -d '{
    "certificate_title": "Introduction to Artificial Intelligence Workshop",
    "organization": "ABC Learning Center",
    "issue_date": "2026-10-11",
    "recipients": [
      {
        "name": "Harshith",
        "email": "harshith@example.com"
      },
      {
        "name": "Aarav Sharma",
        "email": "aarav@example.com"
      },
      {
        "name": "Invalid Participant",
        "email": "not-an-email"
      }
    ]
  }'
```

The API returns HTTP `202 Accepted` and a job ID that can be used to check progress.

Invalid recipients are recorded with validation errors, while valid recipients continue through certificate generation.

## Check Job Status

Use the returned job ID:

```bash
curl "http://127.0.0.1:8000/api/v1/certificate-jobs/YOUR_JOB_ID"
```

The response includes:

- Overall job status
- Total recipient count
- Successful and failed counts
- Progress percentage
- Individual recipient statuses
- Error messages for failed recipients

Possible job statuses include `queued`, `processing`, `completed`, `completed_with_errors`, and `failed`.

## Download Certificates

### Individual PDF

Replace `YOUR_JOB_ID` and `RECIPIENT_ID` with the actual IDs returned by the API.

```bash
curl -L \
  "http://127.0.0.1:8000/api/v1/certificate-jobs/YOUR_JOB_ID/recipients/RECIPIENT_ID/certificate" \
  -o certificate.pdf
```

### ZIP Archive

```bash
curl -L \
  "http://127.0.0.1:8000/api/v1/certificate-jobs/YOUR_JOB_ID/download" \
  -o certificates.zip
```

The ZIP contains the successfully generated certificates for that job.

## Storage

- `certificates.db` stores job and recipient records.
- `storage/certificates/` stores generated PDF certificates.
- `storage/archives/` stores ZIP archives generated for downloads.

## Run Automated Tests

Execute the tests from the project root:

```bash
python3 -m pytest -v
```

The test suite covers:

1. Creating a generation job
2. Input validation
3. Certificate generation
4. Job status and progress
5. Handling an individual certificate generation failure
6. Downloading individual PDFs and ZIP archives

## Design Decisions

### Database

SQLite was chosen because it provides a relational database without requiring a separate database server. SQLAlchemy separates database operations from the API logic.

### Certificate Generation

A single predefined PDF template is generated using ReportLab. Recipient-specific information is inserted into each PDF.

### Bulk Processing

FastAPI `BackgroundTasks` is used to process a submitted job after the API response is returned. This is a simple approach suitable for the assignment, but it is not a durable job queue for production workloads.

### Failure Handling

Each recipient is processed independently. Validation or PDF-generation failures are recorded against the relevant recipient, allowing other valid recipients to continue.

### Progress Tracking

The database stores the job status and each recipient's status. The status endpoint calculates success counts, failure counts, and progress.

### Limitations

The application currently uses a local SQLite database and local file storage. For production deployments involving multiple workers, durable background processing, persistent object storage, and additional operational safeguards would be appropriate.

