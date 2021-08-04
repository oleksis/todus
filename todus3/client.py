import logging
import socket
import string
import time
from pathlib import Path
from typing import Dict, Tuple

import requests
from requests.exceptions import ConnectionError, ConnectTimeout, HTTPError, ReadTimeout
from tqdm.auto import tqdm
from tqdm.utils import CallbackIOWrapper

from todus3 import ErrorCode, __app_name__
from todus3.errors import AbortError
from todus3.s3 import get_real_url, reserve_url
from todus3.util import decode_content, generate_token, shorten_name, tqdm_logging

DEFAULT_TIMEOUT: float = 30  # seconds
CHUNK_SIZE = 1024
logger = logging.getLogger(__app_name__)


class ToDusClient:
    """Class interact with the Todus API."""

    def __init__(
        self, version_name: str = "0.40.16", version_code: str = "21820"
    ) -> None:
        self.version_name = version_name
        self.version_code = version_code

        self.timeout = DEFAULT_TIMEOUT
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept-Encoding": "gzip",
            }
        )
        self.exit = False
        self.error_code = ErrorCode.SUCCESS

    def abort(self) -> None:
        self.session.close()

    @property
    def auth_ua(self) -> str:
        """User Agent used for authentication."""
        return f"ToDus {self.version_name} Auth"

    @property
    def upload_ua(self) -> str:
        """User Agent used for uploads."""
        return f"ToDus {self.version_name} HTTP-Upload"

    @property
    def download_ua(self) -> str:
        """User Agent used for downloads."""
        return f"ToDus {self.version_name} HTTP-Download"

    @property
    def headers_auth(self) -> Dict[str, str]:
        return {
            "Host": "auth.todus.cu",
            "User-Agent": self.auth_ua,
            "Content-Type": "application/x-protobuf",
        }

    def task_request_code(self, phone_number: str) -> None:
        headers = self.headers_auth
        data = (
            b"\n\n"
            + phone_number.encode("utf-8")
            + b"\x12\x96\x01"
            + generate_token(150).encode("utf-8")
        )
        url = "https://auth.todus.cu/v2/auth/users.reserve"
        with self.session.post(url, data=data, headers=headers) as resp:
            resp.raise_for_status()

    def request_code(self, phone_number: str) -> None:
        """Request server to send verification SMS code."""
        self.task_request_code(phone_number)

    def task_validate_code(self, phone_number: str, code: str) -> str:
        content = ""
        headers = self.headers_auth
        data = (
            b"\n\n"
            + phone_number.encode("utf-8")
            + b"\x12\x96\x01"
            + generate_token(150).encode("utf-8")
            + b"\x1a\x06"
            + code.encode("utf-8")
        )
        url = "https://auth.todus.cu/v2/auth/users.register"
        with self.session.post(url, data=data, headers=headers) as resp:
            resp.raise_for_status()
            if b"`" in resp.content:
                index = resp.content.index(b"`") + 1
                content = decode_content(resp.content[index : index + 96])
            else:
                content = decode_content(resp.content[5:166])
        return content

    def validate_code(self, phone_number: str, code: str) -> str:
        """Validate phone number with received SMS code.

        Returns the account password.
        """
        return self.task_validate_code(phone_number, code)

    def task_login(self, phone_number: str, password: str) -> str:
        token = ""
        headers = self.headers_auth
        data = (
            b"\n\n"
            + phone_number.encode("utf-8")
            + b"\x12\x96\x01"
            + generate_token(150).encode("utf-8")
            + b"\x12\x60"
            + password.encode("utf-8")
            + b"\x1a\x05"
            + self.version_code.encode("utf-8")
        )
        url = "https://auth.todus.cu/v2/auth/token"
        with self.session.post(url, data=data, headers=headers) as resp:
            resp.raise_for_status()
            # Default Encoding for HTML4 ISO-8859-1 (Latin-1)
            content = decode_content(resp.content)
            token = "".join(c for c in content if c in string.printable)
        return token

    def login(self, phone_number: str, password: str) -> str:
        """Login with phone number and password to get an access token."""
        return self.task_login(phone_number, password)

    def task_upload_file_1(self, token: str, size: int) -> Tuple[str, str]:
        return reserve_url(token, size)

    def task_upload_file_2(
        self,
        token: str,
        filename_path: Path,
        up_url: str,
        down_url: str,
        timeout: float,
        index: int,
    ) -> str:
        size = filename_path.stat().st_size if filename_path.exists() else 0

        headers = {
            "User-Agent": self.upload_ua,
            "Authorization": f"Bearer {token}",
            "Content-Length": str(size),
        }

        with tqdm(
            total=size,
            desc=f"#{index} {shorten_name(filename_path.name)}",
            unit="B",
            unit_scale=True,
            unit_divisor=CHUNK_SIZE,
        ) as t, open(filename_path, "rb") as fileobj:
            wrapped_file = CallbackIOWrapper(t.update, fileobj, "read")
            with self.session.put(
                url=up_url,
                data=wrapped_file,  # type: ignore
                headers=headers,
                timeout=timeout,
                stream=True,
            ) as resp:
                resp.raise_for_status()
        return down_url

    def upload_file(
        self, token: str, filename_path: Path, index: int = 1, max_retry: int = 3
    ) -> str:
        """Upload data and return the download URL."""
        size = filename_path.stat().st_size if filename_path.exists() else 0
        retry = 0
        up_done = False
        _down_url = ""

        while not up_done and retry < max_retry:
            try:
                up_url, down_url = self.task_upload_file_1(token, size)

                if not up_url:
                    raise ValueError("Upload URL could not be obtained.")

                timeout = max(size / 1024 / 1024 * 20, self.timeout)

                _down_url = self.task_upload_file_2(
                    token, filename_path, up_url, down_url, timeout, index
                )
            except (
                AbortError,
                ConnectionError,
                HTTPError,
                ReadTimeout,
                socket.timeout,
                socket.gaierror,
                ValueError,
            ) as ex:
                tqdm_logging(logging.ERROR, str(ex))
                retry += 1
                tqdm_logging(logging.INFO, f"Retrying: {retry}...")
                if retry == max_retry:
                    self.error_code = ErrorCode.CLIENT
                    tqdm_logging(
                        logging.ERROR,
                        f"Failed to upload part {index} ({size:,} Bytes): {ex}",
                    )
                    self.exit = True
                    break
                time.sleep(5)
            else:
                up_done = True
        return _down_url

    def task_download_1(self, token: str, url: str) -> str:
        url = get_real_url(token, url)
        if not url:
            raise ValueError("Invalid URL 'None'")
        return url

    def task_download_2(
        self,
        token: str,
        url: str,
        filename_path: str,
        down_timeout: float = DEFAULT_TIMEOUT,
    ) -> int:
        headers = {
            "User-Agent": self.download_ua,
            "Authorization": f"Bearer {token}",
        }
        self.timeout = down_timeout
        size = 0
        down_error = False

        with self.session.get(
            url=url, headers=headers, timeout=self.timeout, stream=True
        ) as resp:
            resp.raise_for_status()

            size = int(resp.headers.get("content-length", 0))

            file_save = Path(filename_path)

            overwrite = file_save.stat().st_size < size if file_save.exists() else True
            if overwrite:
                progress_bar = tqdm(
                    miniters=1,
                    total=size,
                    desc=shorten_name(file_save.name),
                    unit="B",
                    unit_scale=True,
                )
                # TODO: Better handle slow connections :(
                # For now we skip slow connections when reach the Timeout
                # https://docs.python-requests.org/en/master/user/quickstart/#timeouts
                with open(file_save, "wb") as file_stream:
                    for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                        if self.exit:
                            break
                        progress_bar.update(len(chunk))
                        file_stream.write(chunk)
                progress_bar.close()
        return size

    def download_file(
        self,
        token: str,
        url: str,
        filename_path: str,
        down_timeout: float = DEFAULT_TIMEOUT,
        max_retry: int = 3,
    ) -> int:
        """Download file URL.

        Returns the file size.
        """
        size = 0
        retry = 0
        down_done = False

        while not down_done and retry < max_retry:
            try:
                url = self.task_download_1(token, url)
                size = self.task_download_2(token, url, filename_path, down_timeout)
            except (
                IOError,
                HTTPError,
                ConnectTimeout,
                ConnectionError,
                ReadTimeout,
                socket.timeout,
                socket.gaierror,
                ValueError,
            ) as ex:
                self.error_code = ErrorCode.CLIENT
                tqdm_logging(logging.ERROR, str(ex))
            else:
                down_done = True

            if not down_done or not size:
                retry += 1
                if retry == max_retry or self.exit:
                    break
                time.sleep(5)
        return size
