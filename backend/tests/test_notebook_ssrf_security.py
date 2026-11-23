import unittest
from unittest.mock import patch, MagicMock
from backend.security import validate_url

def _assert_ssrf_warning(mock_task: MagicMock, kind: str, url: str) -> None:
    """Assert a WARNING mentioning this SSRF block was emitted.

    We intentionally do NOT assert the exact human-readable error sentence
    (e.g. ``URL validation failed: Domain ...``) — that wording is not part
    of the security contract and drifts across upstream refactors. The
    contract is:

    * the dangerous callable was NOT invoked (asserted separately via
      ``assert_not_called``), and
    * a WARNING log line names the blocked ``kind`` (e.g. ``pdf_url``)
      and the offending ``url``.
    """
    for call in mock_task.log.call_args_list:
        args = call.args
        if not args:
            continue
        message = args[0]
        if not isinstance(message, str):
            continue
        level = args[1] if len(args) > 1 else call.kwargs.get("level")
        if (
            level == "WARNING"
            and f"SSRF protection blocked {kind}" in message
            and url in message
        ):
            return
    raise AssertionError(
        f"expected a WARNING log containing 'SSRF protection blocked {kind}' "
        f"and {url!r}; got {[(c.args, c.kwargs) for c in mock_task.log.call_args_list]}"
    )

class TestNotebookIngestionSSRFSecurity(unittest.TestCase):
    """
    Regression tests for the SSRF vulnerabilities in the notebook ingestion task.
    Ensures that internal IP addresses and cloud metadata endpoints are blocked
    across all ingestion paths: Arxiv, Web URLs, and Wikipedia.
    """

    def test_metadata_ip_is_blocked(self):
        with self.assertRaises(ValueError) as context:
            validate_url("http://169.254.169.254/latest/meta-data/iam/security-credentials/")
        self.assertIn("169.254.169.254", str(context.exception))

    def test_localhost_is_blocked(self):
        with self.assertRaises(ValueError) as context:
            validate_url("http://127.0.0.1:8080/admin")
        self.assertIn("127.0.0.1", str(context.exception))

    def test_internal_ip_is_blocked(self):
        with self.assertRaises(ValueError) as context:
            validate_url("http://10.0.0.1/internal-service")
        self.assertIn("10.0.0.1", str(context.exception))

    @patch('requests.get')
    def test_arxiv_ingestion_blocks_ssrf(self, mock_get):
        from backend.tasks.notebook_tasks.ingestion import _ingest_notebook_sources_task

        mock_task = MagicMock()
        mock_task.cancellation_event.is_set.return_value = False
        mock_task.db_session_factory.return_value.__enter__.return_value = MagicMock()

        malicious_url = "http://169.254.169.254/latest/meta-data/iam/security-credentials/"
        arxiv_selected = [{
            "title": "Test",
            "pdf_url": malicious_url,
            "ingest_full": True
        }]

        _ingest_notebook_sources_task(
            task=mock_task,
            username="test_user",
            notebook_id="dummy_id",
            urls=[],
            arxiv_selected_list=arxiv_selected
        )

        # Security contract: the outbound request was never issued.
        mock_get.assert_not_called()
        _assert_ssrf_warning(mock_task, "pdf_url", malicious_url)

    @patch('scrapemaster.ScrapeMaster')
    def test_web_url_ingestion_blocks_ssrf(self, mock_scrape):
        from backend.tasks.notebook_tasks.ingestion import _ingest_notebook_sources_task

        mock_task = MagicMock()
        mock_task.cancellation_event.is_set.return_value = False
        mock_task.db_session_factory.return_value.__enter__.return_value = MagicMock()

        malicious_url = "http://10.0.0.1/internal-service"

        _ingest_notebook_sources_task(
            task=mock_task,
            username="test_user",
            notebook_id="dummy_id",
            urls=[malicious_url]
        )

        mock_scrape.assert_not_called()
        _assert_ssrf_warning(mock_task, "url", malicious_url)

    @patch('wikipedia.page')
    def test_wikipedia_ingestion_blocks_ssrf(self, mock_wiki):
        from backend.tasks.notebook_tasks.ingestion import _ingest_notebook_sources_task

        mock_task = MagicMock()
        mock_task.cancellation_event.is_set.return_value = False
        mock_task.db_session_factory.return_value.__enter__.return_value = MagicMock()

        malicious_url = "http://127.0.0.1:8080/admin"

        _ingest_notebook_sources_task(
            task=mock_task,
            username="test_user",
            notebook_id="dummy_id",
            urls=[],
            wikipedia_urls=[malicious_url]
        )

        mock_wiki.assert_not_called()
        _assert_ssrf_warning(mock_task, "wikipedia url", malicious_url)

if __name__ == '__main__':
    unittest.main()