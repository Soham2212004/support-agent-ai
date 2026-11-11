from django.test import SimpleTestCase

from .public_common import normalize_origin


class NormalizeOriginTests(SimpleTestCase):
    def test_normalizes_scheme_host_and_default_port(self):
        self.assertEqual(normalize_origin("HTTPS://Example.COM:443/"), "https://example.com")

    def test_keeps_non_default_port(self):
        self.assertEqual(normalize_origin("http://localhost:5173"), "http://localhost:5173")

    def test_normalizes_internationalized_domain(self):
        self.assertEqual(normalize_origin("https://münich.example"), "https://xn--mnich-kva.example")

    def test_rejects_non_origin_urls_and_credentials(self):
        for value in (
            "https://example.com/path",
            "https://example.com?next=/",
            "https://user:password@example.com",
            "javascript://example.com",
            "https://bad host.example",
        ):
            with self.subTest(value=value):
                self.assertIsNone(normalize_origin(value))
