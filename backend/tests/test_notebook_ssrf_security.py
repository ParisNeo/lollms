import unittest
from unittest.mock import patch, MagicMock
from backend.security import validate_url

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

    def test_valid_arxiv_url_passes(self):
        try:
            validate_url("https://arxiv.org/pdf/2106.09685")
        except ValueError:
            self.fail("validate_url() raised ValueError unexpectedly for valid arxiv URL!")

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
        
        mock_get.assert_not_called()
        mock_task.log.assert_any_call(
            f"SSRF protection blocked pdf_url {malicious_url}: URL validation failed: Domain 169.254.169.254 resolves to private IP 169.254.169.254.",
            "WARNING"
        )

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
        mock_task.log.assert_any_call(
            f"SSRF protection blocked url {malicious_url}: URL validation failed: Domain 10.0.0.1 resolves to private IP 10.0.0.1.",
            "WARNING"
        )

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
        mock_task.log.assert_any_call(
            f"SSRF protection blocked wikipedia url {malicious_url}: URL validation failed: Domain 127.0.0.1 resolves to private IP 127.0.0.1.",
            "WARNING"
        )

if __name__ == '__main__':
    unittest.main()
