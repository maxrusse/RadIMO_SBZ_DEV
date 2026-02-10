import unittest
from unittest.mock import patch

from flask import Flask

from routes import routes


class TestHealthEndpoints(unittest.TestCase):
    def setUp(self) -> None:
        app = Flask(__name__, template_folder="../templates")
        app.secret_key = "test-secret"
        app.register_blueprint(routes)
        self.client = app.test_client()

    def test_healthz_returns_ok(self) -> None:
        response = self.client.get("/healthz")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["service"], "RadIMO Cortex")
        self.assertIn("timestamp", payload)

    @patch("routes.run_operational_checks")
    def test_readyz_returns_200_when_no_errors(self, mock_checks) -> None:
        mock_checks.return_value = {
            "results": [
                {"name": "Config File", "status": "OK", "detail": "Loaded"},
                {"name": "Worker Data", "status": "WARNING", "detail": "No workers"},
            ],
            "timestamp": "2026-02-10T12:00:00+01:00",
        }

        response = self.client.get("/readyz")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["summary"]["error"], 0)

    @patch("routes.run_operational_checks")
    def test_readyz_returns_503_when_error_exists(self, mock_checks) -> None:
        mock_checks.return_value = {
            "results": [
                {"name": "Upload Folder", "status": "ERROR", "detail": "Not writable"},
            ],
            "timestamp": "2026-02-10T12:00:00+01:00",
        }

        response = self.client.get("/readyz")

        self.assertEqual(response.status_code, 503)
        payload = response.get_json()
        self.assertEqual(payload["status"], "not_ready")
        self.assertEqual(payload["summary"]["error"], 1)

    @patch("routes.run_operational_checks")
    def test_status_page_renders(self, mock_checks) -> None:
        mock_checks.return_value = {
            "results": [
                {"name": "Config File", "status": "OK", "detail": "Loaded"},
            ],
            "timestamp": "2026-02-10T12:00:00+01:00",
        }

        response = self.client.get("/status")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Readiness Checks", response.data)


if __name__ == "__main__":
    unittest.main()
