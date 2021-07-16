import random
import string


def generate_token(length: int) -> str:
    """Generate random alphanumeric string of the requested lenght."""
    chars = string.ascii_letters + string.digits
    return "".join(random.choice(chars) for _ in range(length))
