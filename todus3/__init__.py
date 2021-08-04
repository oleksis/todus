from enum import IntEnum


__app_name__ = "todus3"
__version__ = "0.9.0"


class ErrorCode(IntEnum):
    SUCCESS = 0
    CLIENT = 10
    MAIN = 20

    def __str__(self) -> str:
        return str(self.value)
