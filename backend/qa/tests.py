from unittest.mock import patch

from django.test import TestCase


class AskViewTests(TestCase):
    @patch("qa.views.answer_with_judgement", return_value=(False, "测试回答"))
    def test_answerable(self, _mock):
        resp = self.client.post("/api/ask/", {"question": "怎么做缓存？"}, content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"refused": False, "answer": "测试回答"})

    @patch("qa.views.answer_with_judgement", return_value=(True, "[NO_ANSWER]"))
    def test_refused(self, _mock):
        resp = self.client.post("/api/ask/", {"question": "今天股市怎么样？"}, content_type="application/json")
        self.assertEqual(resp.json(), {"refused": True, "answer": None})

    def test_empty_question(self):
        resp = self.client.post("/api/ask/", {"question": "  "}, content_type="application/json")
        self.assertEqual(resp.status_code, 400)