"""RED test — strict schema for scheduled provider inbox reports (Pydantic v2)."""
from __future__ import annotations

import unittest

from pydantic import ValidationError

from backend.app.inbox.schema import ScheduledReport

VALID_REPORT = {
    "schema_version": "1",
    "run_id": "provider-2026-10-25T07-00-00+07-00",
    "report_kind": "provider_harness_radar",
    "observed_at": "2026-10-25T07:00:00+07:00",
    "timezone": "Asia/Ho_Chi_Minh",
    "findings": [{
        "external_id": "finding-1",
        "title": "Safe title",
        "category": "AI & Model",
        "summary": "Safe source-grounded summary.",
        "canonical_urls": ["https://official.example.test/news"],
        "source_type": "official",
        "verification_status": "UNVERIFIED",
        "evidence_note": "Official documentation observed.",
        "valid_until": None,
        "risk_note": None,
    }],
}


def _copy_report(**overrides):
    report = dict(VALID_REPORT)
    for key, value in overrides.items():
        report[key] = value
    return report


def _copy_finding(index: int, **overrides):
    findings = [dict(f) for f in VALID_REPORT["findings"]]
    findings[index] = {**findings[index], **overrides}
    return findings


class TestScheduledReportV1(unittest.TestCase):
    def test_valid_report_v1_parses(self):
        report = ScheduledReport.model_validate({
            "schema_version": "1",
            "run_id": "provider-2026-10-25T07-00-00+07-00",
            "report_kind": "provider_harness_radar",
            "observed_at": "2026-10-25T07:00:00+07:00",
            "timezone": "Asia/Ho_Chi_Minh",
            "findings": [{
                "external_id": "finding-1",
                "title": "Safe title",
                "category": "AI & Model",
                "summary": "Safe source-grounded summary.",
                "canonical_urls": ["https://official.example.test/news"],
                "source_type": "official",
                "verification_status": "UNVERIFIED",
                "evidence_note": "Official documentation observed.",
                "valid_until": None,
                "risk_note": None,
            }],
        })
        self.assertEqual(report.schema_version, "1")

    # ---- extra='forbid' -------------------------------------------------

    def test_unknown_top_level_field_rejected(self):
        with self.assertRaises(ValidationError):
            ScheduledReport.model_validate(_copy_report(injected_extra="drop table"))

    def test_unknown_finding_field_rejected(self):
        with self.assertRaises(ValidationError):
            ScheduledReport.model_validate(
                _copy_report(findings=_copy_finding(0, shell_command="echo pwned"))
            )

    # ---- report_kind ----------------------------------------------------

    def test_both_report_kinds_accepted(self):
        for kind in ("provider_harness_radar", "tip_trick_radar"):
            with self.subTest(kind=kind):
                report = ScheduledReport.model_validate(_copy_report(report_kind=kind))
                self.assertEqual(report.report_kind, kind)

    def test_unknown_report_kind_rejected(self):
        with self.assertRaises(ValidationError):
            ScheduledReport.model_validate(_copy_report(report_kind="weekly_digest"))

    # ---- canonical_urls --------------------------------------------------

    def test_empty_canonical_urls_rejected(self):
        with self.assertRaises(ValidationError):
            ScheduledReport.model_validate(
                _copy_report(findings=_copy_finding(0, canonical_urls=[]))
            )

    def test_non_http_scheme_rejected(self):
        for url in ("ftp://example.test/x", "file:///etc/passwd", "javascript:alert(1)"):
            with self.subTest(url=url):
                with self.assertRaises(ValidationError):
                    ScheduledReport.model_validate(
                        _copy_report(findings=_copy_finding(0, canonical_urls=[url]))
                    )

    def test_userinfo_url_rejected(self):
        with self.assertRaises(ValidationError):
            ScheduledReport.model_validate(
                _copy_report(
                    findings=_copy_finding(
                        0, canonical_urls=["https://user:pass@example.test/x"]
                    )
                )
            )

    def test_http_scheme_accepted(self):
        report = ScheduledReport.model_validate(
            _copy_report(
                findings=_copy_finding(0, canonical_urls=["http://example.test/x"])
            )
        )
        self.assertEqual(report.findings[0].canonical_urls, ["http://example.test/x"])

    # ---- observed_at / valid_until ---------------------------------------

    def test_naive_observed_at_rejected(self):
        with self.assertRaises(ValidationError):
            ScheduledReport.model_validate(
                _copy_report(observed_at="2026-10-25T07:00:00")
            )

    def test_invalid_observed_at_rejected(self):
        for value in ("not-a-date", "2026-13-45T07:00:00+07:00", ""):
            with self.subTest(observed_at=value):
                with self.assertRaises(ValidationError):
                    ScheduledReport.model_validate(_copy_report(observed_at=value))

    def test_offset_observed_at_accepted(self):
        for value in ("2026-10-25T00:00:00+00:00", "2026-10-25T07:00:00+07:00"):
            with self.subTest(observed_at=value):
                report = ScheduledReport.model_validate(_copy_report(observed_at=value))
                self.assertIsNotNone(report.observed_at.utcoffset())

    def test_non_null_valid_until_rejected(self):
        with self.assertRaises(ValidationError):
            ScheduledReport.model_validate(
                _copy_report(
                    findings=_copy_finding(0, valid_until="2026-11-01T00:00:00+07:00")
                )
            )

    # ---- enums ------------------------------------------------------------

    def test_source_types_accepted(self):
        for source in ("official", "community", "account_probe"):
            with self.subTest(source_type=source):
                report = ScheduledReport.model_validate(
                    _copy_report(findings=_copy_finding(0, source_type=source))
                )
                self.assertEqual(report.findings[0].source_type, source)

    def test_unknown_source_type_rejected(self):
        for source in ("rumor", "OFFICIAL", ""):
            with self.subTest(source_type=source):
                with self.assertRaises(ValidationError):
                    ScheduledReport.model_validate(
                        _copy_report(findings=_copy_finding(0, source_type=source))
                    )

    def test_verification_statuses_accepted(self):
        for status in ("VERIFIED", "UNVERIFIED", "NEEDS_REVIEW"):
            with self.subTest(verification_status=status):
                report = ScheduledReport.model_validate(
                    _copy_report(
                        findings=_copy_finding(0, verification_status=status)
                    )
                )
                self.assertEqual(report.findings[0].verification_status, status)

    def test_unknown_verification_status_rejected(self):
        for status in ("STALE", "verified", ""):
            with self.subTest(verification_status=status):
                with self.assertRaises(ValidationError):
                    ScheduledReport.model_validate(
                        _copy_report(findings=_copy_finding(0, verification_status=status))
                    )


if __name__ == "__main__":
    unittest.main()
