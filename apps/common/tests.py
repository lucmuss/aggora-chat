from django.test import TestCase
from django.urls import reverse


class CommonFeatureTests(TestCase):
    def test_manifest_exposes_install_metadata(self):
        response = self.client.get(reverse("web_manifest"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/manifest+json")
        self.assertContains(response, '"name": "Agora"')

    def test_service_worker_is_served_as_javascript(self):
        response = self.client.get(reverse("service_worker"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("application/javascript", response["Content-Type"])
        self.assertContains(response, "CACHE_NAME")

    def test_markdown_preview_renders_html(self):
        response = self.client.post(reverse("markdown_preview"), {"markdown": "## Preview"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<h2>Preview</h2>", html=True)
