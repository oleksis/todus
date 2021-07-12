import logging
import string
from typing import Any, Callable, Dict, Optional, Tuple

import requests

from . import __app_name__
from .s3 import get_real_url, reserve_url
from .util import ResultProcess, generate_token


logger = logging.getLogger(__app_name__)


class ToDusClient:
    def __init__(
        self, version_name: str = "0.40.16", version_code: str = "21820"
    ) -> None:
        self.version_name = version_name
        self.version_code = version_code

        self.timeout = 60
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept-Encoding": "gzip",
            }
        )
        self._real_request = self.session.request
        self.session.request = self._request  # type: ignore[assignment]
        self._process: Optional[ResultProcess] = None

    def _request(self, *args, **kwargs) -> requests.Response:
        kwargs.setdefault("timeout", self.timeout)
        return self._real_request(*args, **kwargs)

    def _run_task(self, task: Callable, timeout: float, **kwargs) -> Any:
        self._process = ResultProcess(target=task, **kwargs)
        try:
            self._process.start()
            return self._process.get_result(timeout)
        except (AttributeError, PermissionError) as ex:
            # AttributeError: Can't pickle local object 'ToDusClient.login.<locals>.task'
            logger.exception(ex)
            self.abort()

    def abort(self) -> None:
        if self._process is not None and self._process.is_alive():
            self._process.terminate()
            self._process.abort()
            self._process = None

    @property
    def auth_ua(self) -> str:
        return f"ToDus {self.version_name} Auth"

    @property
    def upload_ua(self) -> str:
        return f"ToDus {self.version_name} HTTP-Upload"

    @property
    def download_ua(self) -> str:
        return f"ToDus {self.version_name} HTTP-Download"

    @property
    def headers_auth(self) -> Dict[str, str]:
        return {
            "Host": "auth.todus.cu",
            "User-Agent": self.auth_ua,
            "Content-Type": "application/x-protobuf",
        }

    def task_request_code(self, phone_number: str) -> None:
        # TODO: Fix payload/data
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
        kwargs = {"args": (phone_number,)}
        self._run_task(self.task_request_code, self.timeout, **kwargs)

    def task_validate_code(self, phone_number: str, code: str) -> str:
        # TODO: Fix payload/data
        headers = self.headers_auth
        data = (
            b"\n\n"
            + phone_number.encode("utf-8")
            + b"\x12\x96\x01"
            + generate_token(150).encode("utf-8")
            + b"\x1a\x06"
            + code.encode()
        )
        url = "https://auth.todus.cu/v2/auth/users.register"
        with self.session.post(url, data=data, headers=headers) as resp:
            resp.raise_for_status()
            if b"`" in resp.content:
                index = resp.content.index(b"`") + 1
                return resp.content[index : index + 96].decode()
            else:
                return resp.content[5:166].decode()

    def validate_code(self, phone_number: str, code: str) -> str:
        """Validate phone number with received SMS code.

        Returns the account password.
        """
        kwargs = {"args": (phone_number, code)}
        return self._run_task(self.task_validate_code, self.timeout, **kwargs)

    def task_login(self, phone_number: str, password: str) -> str:
        # TODO: Fix payload/data
        headers = self.headers_auth
        data = (
            b"\n\n"
            + phone_number.encode()
            + b"\x12\x96\x01"
            + generate_token(150).encode("utf-8")
            + b"\x12\x60"
            + password.encode()
            + b"\x1a\x05"
            + self.version_code.encode("utf-8")
        )
        url = "https://auth.todus.cu/v2/auth/token"
        with self.session.post(url, data=data, headers=headers) as resp:
            resp.raise_for_status()
            token = "".join([c for c in resp.text if c in string.printable])
            return token

    def login(self, phone_number: str, password: str) -> str:
        """Login with phone number and password to get an access token."""
        kwargs = {"args": (phone_number, password)}
        return self._run_task(self.task_login, self.timeout, **kwargs)

    def task_upload_file_1(self, token: str, size: int) -> Tuple[str, str]:
        return reserve_url(token, size)

    def task_upload_file_2(
        self, token: str, data: bytes, up_url: str, down_url: str, timeout: float
    ) -> str:
        headers = {
            "User-Agent": self.upload_ua,
            "Authorization": f"Bearer {token}",
        }
        with self.session.put(
            url=up_url, data=data, headers=headers, timeout=timeout
        ) as resp:
            resp.raise_for_status()
        return down_url

    def upload_file(self, token: str, data: bytes, size: int = None) -> str:
        """Upload data and return the download URL."""
        if size is None:
            size = len(data)

        kwargs = {"args": (token, size)}
        up_url, down_url = self._run_task(
            self.task_upload_file_1, self.timeout, **kwargs
        )

        timeout = max(len(data) / 1024 / 1024 * 20, self.timeout)

        kwargs = {"args": (token, data, up_url, down_url, timeout)}  # type: ignore [dict-item]
        return self._run_task(self.task_upload_file_2, timeout, **kwargs)

    def task_download_1(self, token, url) -> str:
        return get_real_url(token, url)

    def task_download_2(self, token, url, path) -> int:
        headers = {
            "User-Agent": self.download_ua,
            "Authorization": f"Bearer {token}",
        }
        with self.session.get(url=url, headers=headers) as resp:
            resp.raise_for_status()
            size = int(resp.headers.get("Content-Length", 0))
            with open(path, "wb") as file:
                file.write(resp.content)
            return size

    def download_file(
        self, token: str, url: str, path: str, down_timeout: float = 60 * 20
    ) -> int:
        """Download file URL.

        Returns the file size.
        """
        kwargs = {"args": (token, url)}
        url = self._run_task(self.task_download_1, self.timeout, **kwargs)
        kwargs = {"args": (token, url, path)}  # type: ignore [dict-item]
        return self._run_task(self.task_download_2, down_timeout, **kwargs)
