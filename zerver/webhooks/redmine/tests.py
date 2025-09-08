from zerver.lib.test_classes import WebhookTestCase


class RedmineHookTests(WebhookTestCase):
    STREAM_NAME = "redmine"
    URL_TEMPLATE = "/api/v1/external/redmine?api_key={{api_key}}"
    FIXTURE_DIR_NAME = "redmine"

    def test_opened(self) -> None:
        expected_topic_name = "TestProject #123: Test Issue Subject"
        expected_message = (
            "Vmeetx created issue [#123: Test Issue Subject](http://example.com/issues/123) "
            "with status **New** and priority **Normal**.\n"
            "> This is the issue description."
        )
        self.check_webhook(
            "issue_opened",
            expected_topic_name,
            expected_message,
            content_type="application/json",
        )

    def test_updated(self) -> None:
        expected_topic_name = "TestProject #123: Test Issue Subject"
        expected_message = (
            "Vmeetx updated issue [#123: Test Issue Subject](http://example.com/issues/123).\n"
            "> This is a note added to the issue."
        )
        self.check_webhook(
            "issue_updated",
            expected_topic_name,
            expected_message,
            content_type="application/json",
        )

    def test_unknown_event(self) -> None:
        url = self.build_webhook_url()
        payload = {"payload": {"action": "closed", "other_data": "irrelevant"}}
        result = self.client_post(url, payload, content_type="application/json")
        self.assert_json_success(result)

    def test_malformed_json(self) -> None:
        url = self.build_webhook_url()
        result = self.client_post(
            url,
            '{ invalid json content: }',
            content_type="application/json"
        )
        self.assert_json_success(result)

    def test_missing_action(self) -> None:
        url = self.build_webhook_url()
        payload = {"payload": {"issue": {"id": 999, "subject": "Test"}}}
        result = self.client_post(url, payload, content_type="application/json")
        self.assert_json_success(result)