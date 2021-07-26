import sys
from pathlib import Path
from unittest import TestCase
from unittest.mock import MagicMock, patch

HERE = Path(__file__).parent
PACKAGE_PATH = HERE.parent
sys.path.insert(0, str(PACKAGE_PATH))


from todus3.util import generate_token, shorten_name, normalize_phone_number


class TestUtil(TestCase):
    @patch("random.choice")
    def test_generate_token(self, mock_random_choice: MagicMock):
        lenght: int = 150
        expected = (
            "XSvRz21yqf0KiMZEIiijWZiZWJKZCzPwR6RPiaYfIfJ5Wj0lVX"
            "cT9gIynyQmDstQ5gce5uJ4Lm8lLzaaEjRdeqsRGVQ3QeT6Rr2n"
            "ntaqIr8TiQZHDyP8BgXgD7qO0ZTsshznVG08MrdbiK42ldUxJj"
        )

        mock_random_choice.side_effect = (ch for ch in expected)
        result = generate_token(150)

        mock_random_choice.assert_called()
        self.assertEqual(mock_random_choice.call_count, 150)
        self.assertEqual(result, expected)
        self.assertEqual(len(result), len(expected))

    def test_shorten_name(self):
        name = "Rust Books.zip"
        self.assertEqual(shorten_name(name), "Rust Books.zip")
        name = "PREMIOS JUVENTUD 2021 @TVAdictosS3.part17.rar"
        sh_name = shorten_name(name)
        self.assertEqual(sh_name, "PREMIOS JU...t17.rar")
        self.assertEqual(len(sh_name), 20)
        name = "Docker Desktop Installer.exe.7z.0001"
        sh_name = shorten_name(name)
        self.assertEqual(sh_name, "Docker Des...7z.0001")
        self.assertEqual(len(sh_name), 20)

    def test_normalize_phone_number(self):
        ph_number = "+53 52123456"
        expected = "5352123456"
        self.assertEqual(normalize_phone_number(ph_number), expected)
        ph_number = "52 123456"
        self.assertEqual(normalize_phone_number(ph_number), expected)
        ph_number = "53 52 123456"
        expected = "5353521234"
        self.assertEqual(normalize_phone_number(ph_number), expected)
        ph_number = "+53 52 1234"
        with self.assertRaises(AssertionError) as error:
            normalize_phone_number(ph_number)
            self.assertEqual(error.msg, "Invalid phone number")  # type: ignore
