import logging
import random
import re
import string
from functools import wraps

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
