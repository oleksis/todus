import logging
import socket
import string
from queue import Empty, Queue
from typing import Any, Callable, Dict, Optional, Tuple

import requests

from .errors import AbortError
from .s3 import get_real_url, reserve_url
from .util import generate_token

DEFAULT_TIMEOUT = 60 * 2  # 2 minutes
logger = logging.getLogger(__name__)


class ResultProcess:
    def __init__(self, target, *args, **kwargs) -> None:
        self._real_target = target
        self.args = args
        self.kwargs = kwargs
        self._result_queue: Queue = Queue()
        self._failed = False

    def start(self, *args, **kwargs) -> None:
        try:
            self._result_queue.put(self._real_target(*args, **kwargs))
        except Exception as ex:
            self._failed = True
            self._result_queue.put(ex)

    def abort(self) -> None:
        self._failed = True
        self._result_queue.put(AbortError())

    def get_result(self, timeout: float = None):
        result = None
        try:
            result = self._result_queue.get(timeout=timeout)
        except Empty:
            raise TimeoutError("Operation timed out.")
        if self._failed:
            raise result
        return result


class ToDusClient:
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
        self._process: Optional[ResultProcess] = None

    def _run_task(self, task: Callable, timeout: float, *args, **kwargs) -> Any:
        self._process = ResultProcess(task, *args, **kwargs)
        try:
            self._process.start(*args, **kwargs)
            return self._process.get_result(timeout)
        except Exception as ex:
            logger.exception(ex)
            self.abort()

    def abort(self) -> None:
        if self._process is not None:
            self._process.abort()
            self._process = None
        self.session.close()

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
        args = (phone_number,)
        self._run_task(self.task_request_code, self.timeout, *args)

    def task_validate_code(self, phone_number: str, code: str) -> str:
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
        args = (
            phone_number,
            code,
        )
        return self._run_task(self.task_validate_code, self.timeout, *args)

    def task_login(self, phone_number: str, password: str) -> str:
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
        args = (
            phone_number,
            password,
        )
        return self._run_task(self.task_login, self.timeout, *args)

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

        args = (
            token,
            size,
        )
        up_url, down_url = self._run_task(self.task_upload_file_1, self.timeout, *args)

        timeout = max(len(data) / 1024 / 1024 * 20, self.timeout)

        args_2 = (token, data, up_url, down_url, timeout)
        return self._run_task(self.task_upload_file_2, timeout, *args_2)

    def task_download_1(self, token: str, url: str) -> str:
        try:
            url = get_real_url(token, url)
        except socket.timeout as ex:
            logger.exception(ex)
        if not url:
            raise ValueError("Invalid URL 'None'")
        return url

    def task_download_2(self, token: str, url: str, path: str) -> int:
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
        args = (
            token,
            url,
        )
        url = self._run_task(self.task_download_1, self.timeout, *args)
        args_2 = (
            token,
            url,
            path,
        )
        return self._run_task(self.task_download_2, down_timeout, *args_2)
