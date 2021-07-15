import socket
import sys
from pathlib import Path
from unittest import TestCase
from unittest.mock import MagicMock, call, patch

HERE = Path(__file__).parent
PACKAGE_PATH = HERE.parent
sys.path.insert(0, str(PACKAGE_PATH))


from todus.s3 import _get_socket, _parse_token


class TestS3(TestCase):
    TOKEN = (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE2MjU5N"
        "jkyOTgsInVzZXJuYW1lIjoiNTM1MjM0NTY3OCIsInZlcnNpb24iOiI"
        "yMTgyMCJ9.r3W6-4gLiva_ty1G_JKZKzwAL-8vicy-BHumW-W6bqg"
    )

    @patch("todus.s3.ssl")
    @patch("todus.s3.socket")
    def test_get_socket(self, mock_socket: MagicMock, mock_ssl_socket: MagicMock):
        mock_socket.socket = MagicMock(spec=socket.socket)

        so = _get_socket()

        settimeout = mock_socket.mock_calls[1]
        wrap_socket = mock_ssl_socket.mock_calls[0]
        connect = mock_ssl_socket.mock_calls[1]
        send = mock_ssl_socket.mock_calls[2]

        mock_socket.socket.assert_called_once_with(mock_socket.AF_INET)
        name, args, _ = settimeout
        self.assertEqual((name, args), ("socket().settimeout", (15,)))

        name, args, kwargs = wrap_socket
        self.assertTrue("ssl_version" in kwargs, "Set `ssl_version` kwargs")
        self.assertTrue(
            "ssl.PROTOCOL_TLSv1_2" in str(kwargs.get("ssl_version")),
            "Use ssl.PROTOCOL_TLSv1_2",
        )

        self.assertEqual(connect.args, (("im.todus.cu", 1756),))
        self.assertEqual(
            send.args,
            (b"<stream:stream xmlns='jc' o='im.todus.cu' xmlns:stream='x1' v='1.0'>",),
        )

    def test_parse_token(self):
        phone: str = "5352345678"
        password_auth: bytes = (
            "ADUzNTIzNDU2NzgAZXlKaGJHY2lPaUpJVXpJMU5pSXNJblI1Y0NJNklrcFhWQ0o"
            "5LmV5SmxlSEFpT2pFMk1qVTVOamt5T1Rnc0luVnpaWEp1WVcxbElqb2lOVE0xTW"
            "pNME5UWTNPQ0lzSW5abGNuTnBiMjRpT2lJeU1UZ3lNQ0o5LnIzVzYtNGdMaXZhX"
            "3R5MUdfSktaS3p3QUwtOHZpY3ktQkh1bVctVzZicWc="
        ).encode("utf-8")
        self.assertTupleEqual(
            _parse_token(self.TOKEN),
            (
                phone,
                password_auth,
            ),
        )
