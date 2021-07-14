import sys
from pathlib import Path
from unittest import TestCase
from unittest.mock import MagicMock, patch

HERE = Path(__file__).parent
PACKAGE_PATH = HERE.parent
sys.path.insert(0, str(PACKAGE_PATH))


from todus.util import generate_token


class TestUtil(TestCase):
    @patch("random.choice")
    def test_generate_token(self, mock_random_choice: MagicMock):
        lenght: int = 150
        expected = (
            "XSvRz21yqf0KiMZEIiijWZiZWJKZCzPwR6RPiaYfIfJ5Wj0l"
            "VXcT9gIynyQmDstQ5gce5uJ4Lm8lLzaaEjRdeqsRGVQ3QeT6"
            "Rr2nntaqIr8TiQZHDyP8BgXgD7qO0ZTsshznVG08MrdbiK42ldUxJj"
        )

        mock_random_choice.side_effect = (ch for ch in expected)
        result = generate_token(150)

        mock_random_choice.assert_called()
        self.assertEqual(result, expected)
        self.assertEqual(len(result), len(expected))
