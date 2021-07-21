import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
PACKAGE_PATH = HERE.parent
sys.path.insert(0, str(PACKAGE_PATH))


try:
    from PyInstaller import __main__ as main_pyinstaller
    from PyInstaller import compat as pyi_compat

    if pyi_compat.is_win:
        from PyInstaller.utils.win32.versioninfo import (
            FixedFileInfo,
            SetVersion,
            StringFileInfo,
            StringStruct,
            StringTable,
            VarFileInfo,
            VarStruct,
            VSVersionInfo,
        )
except ImportError:
    pyi_compat = None
    print("Cannot import pyinstaller", file=sys.stderr)
    exit(1)


def version2tuple(version, review=0):
    version_list = str(version).split(".")
    if len(version_list) > 3:
        _review = int(version_list[3])
        del version_list[3]
    else:
        _review = review

    major, minor, patch = [int(value) for value in version_list]
    return major, minor, patch, _review


def version2str(version, review=0):
    version_tuple = version2tuple(version, review)
    return "%s.%s.%s.%s" % version_tuple


pyproyect_toml = Path(PACKAGE_PATH / Path("pyproject.toml")).read_text(encoding="utf-8")

match_search = re.search(r"name\s+=\s(?P<name>.*)?", pyproyect_toml)
NAME = match_search.group("name").strip(' "') if match_search else ""

match_search = re.search(r"maintainers\s+=\s(?P<maintainers>.*)?", pyproyect_toml)
MAINTAINER = match_search.group("maintainers").strip() if match_search else ""
MAINTAINER_EMAIL = MAINTAINER.split("<", maxsplit=1)[-1].strip(' >"]')

match_search = re.search(r"description\s+=\s(?P<desc>.*)?", pyproyect_toml)
DESCRIPTION = match_search.group("desc").strip(' "') if match_search else ""

match_search = re.search(r"homepage\s+=\s(?P<homepage>.*)?", pyproyect_toml)
HOME_PAGE = match_search.group("homepage").strip(' "') if match_search else ""

LONG_DESCRIPTION = open(PACKAGE_PATH / Path("README.md"), "r", encoding="utf-8").read()

# Get the version from NAME/__init__.py without importing the package
version_namespace = {}
with open(PACKAGE_PATH / Path(f"{NAME}/__init__.py"), "r", encoding="utf-8") as fp:
    exec(fp.read(), version_namespace)

__version__ = version_namespace.get("__version__", "0.0.0")
__version_tuple__ = version2tuple(__version__)
__version_str__ = version2str(__version__)
version_file = None

if pyi_compat and pyi_compat.is_win:
    version_file = VSVersionInfo(
        ffi=FixedFileInfo(
            filevers=__version_tuple__,
            prodvers=__version_tuple__,
            mask=0x3F,
            flags=0x0,
            OS=0x4,
            fileType=0x1,
            subtype=0x0,
            date=(0, 0),
        ),
        kids=[
            VarFileInfo([VarStruct("Translation", [0, 1200])]),
            StringFileInfo(
                [
                    StringTable(
                        "000004b0",
                        [
                            StringStruct("CompanyName", MAINTAINER_EMAIL),
                            StringStruct("FileDescription", DESCRIPTION),
                            StringStruct("FileVersion", __version_str__),
                            StringStruct("InternalName", f"{NAME}.exe"),
                            StringStruct(
                                "LegalCopyright",
                                f"{HOME_PAGE}/LICENSE",
                            ),
                            StringStruct("OriginalFilename", f"{NAME}.exe"),
                            StringStruct("ProductName", NAME),
                            StringStruct("ProductVersion", __version_str__),
                        ],
                    )
                ]
            ),
        ],
    )


if __name__ == "__main__":
    main_pyinstaller.run(
        [
            f"{PACKAGE_PATH}/{NAME}/__main__.py",
            "-c",
            "-F",
            "--exclude-module=tests",
            f"--name={NAME}",
        ]
    )

    if version_file:
        time.sleep(3)
        SetVersion(f"{PACKAGE_PATH}/dist/{NAME}.exe", version_file)
