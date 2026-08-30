from app.cli import _redact_database_url, doctor


def test_doctor_is_secret_safe_and_describes_postgres_queue() -> None:
    report = doctor()

    assert report["execution_mode"]["value"] == "PAPER"
    assert "Redis is not required" in report["queue"]["detail"]
    assert "mercury" in report["database"]["value"]
    assert "[REDACTED]" in report["database"]["value"]


def test_database_url_redaction_preserves_no_password() -> None:
    assert _redact_database_url("postgresql://user:secret@db:5432/mercury") == (
        "postgresql://user:[REDACTED]@db:5432/mercury"
    )
