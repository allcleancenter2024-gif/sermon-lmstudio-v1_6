import unittest
from unittest.mock import patch

from app.providers.lmstudio import LMStudioClient, cancel_generation


class V43GenerationCancelTests(unittest.TestCase):
    def test_registered_generation_can_be_cancelled_without_deleting_model(self):
        client = LMStudioClient("http://127.0.0.1:12345/v1")
        client.begin_generation("test-generation")
        with patch.object(client, "cancel", wraps=client.cancel) as cancel:
            self.assertTrue(cancel_generation("test-generation"))
            cancel.assert_called_once_with()
        self.assertTrue(client._cancel_event.is_set())
        client.end_generation()
        self.assertFalse(cancel_generation("test-generation"))


if __name__ == "__main__":
    unittest.main()
