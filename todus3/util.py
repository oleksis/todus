import logging
import random
import re
import string
from functools import wraps
from typing import TYPE_CHECKING

from requests.exceptions import HTTPError
from tqdm.contrib.logging import logging_redirect_tqdm

if TYPE_CHECKING:
    from requests import Response

logger = logging.getLogger(__name__)


def generate_token(length: int) -> str:
    """Generate random alphanumeric string of the requested lenght."""
    chars = string.ascii_letters + string.digits
    return "".join(random.choice(chars) for _ in range(length))


def shorten_name(name: str) -> str:
    """Shorten name to lenght = 20"""
    if len(name) > 20:
        name = f"{name[:10]}...{name[-7:]}"
    return name


def decode_content(resp_content: bytes) -> str:
    # We attempt to decode utf-8 first because some servers
    # choose to localize their response strings. If the string
    # isn't utf-8, we fall back to iso-8859-1 for all other
    # encodings.
    try:
        content = resp_content.decode("utf-8")
    except UnicodeDecodeError:
        content = resp_content.decode("iso-8859-1")
    return content


def tqdm_logging(level: int = logging.DEBUG, message: str = "") -> None:
    """Redirecting console logging to `tqdm.write()`"""
    with logging_redirect_tqdm([logger]):
        if level == logging.DEBUG:
            logger.debug(message)
        elif level == logging.WARNING:
            logger.warning(message)
        elif level == logging.ERROR:
            logger.error(message)
        elif level == logging.FATAL:
            logger.fatal(message)
        elif level == logging.CRITICAL:
            logger.critical(message)
        else:
            logger.info(message)


def raise_for_status(response: "Response"):
    try:
        response.raise_for_status()
    except HTTPError as ex:
        tqdm_logging(logging.ERROR, str(ex))


def normalize_phone_number(phone_number: str) -> str:
    """Normalize phone number with Cuba contry code"""
    phone_number = phone_number.replace(" ", "")
    m = re.match(r"(\+53)?(?P<number>\d{8})", phone_number)
    assert m is not None, "Invalid phone number"
    number = f'53{m.group("number")}'
    assert len(number) == 10, "Phone number requires 10 digits"
    return number


def catch_exceptions_decorator(func):
    """Decorator that catch exception"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except (KeyboardInterrupt, Exception) as ex:
            logger.error(ex)

    return wrapper
