import argparse
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from configparser import ConfigParser
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import RLock as TRLock
from typing import Any, Dict, List, Optional, Union
from urllib.parse import quote_plus, unquote_plus

try:
    import multivolumefile
    import py7zr
except ImportError:
    multivolumefile = None
    py7zr = None
from tqdm.auto import tqdm

from todus3 import ErrorCode, __app_name__, __version__
from todus3.client import ToDusClient
from todus3.util import normalize_phone_number, tqdm_logging

formatter = logging.Formatter("%(levelname)s-%(name)s-%(asctime)s-%(message)s")
logger = logging.getLogger(__app_name__)
logger.setLevel(logging.DEBUG)
handler_default = logging.StreamHandler()
handler_default.setFormatter(formatter)
handler_error = logging.FileHandler("logs", encoding="utf-8")
handler_error.setLevel(logging.ERROR)
handler_error.setFormatter(formatter)
logger.addHandler(handler_default)
logger.addHandler(handler_error)

config = ConfigParser()
MAX_RETRY = 3
DOWN_TIMEOUT = 30  # seconds
MAX_WORKERS = 3
PY3_7 = sys.version_info[:2] >= (3, 7)


def write_txt(filename: str, urls: List[str], parts: List[str]) -> str:
    txt = "\n".join(f"{down_url}\t{name}" for down_url, name in zip(urls, parts))
    path = Path(f"{filename}.txt").resolve()
    with open(path, "w", encoding="utf-8") as f:
        f.write(txt)
    return str(path)


def split_upload(
    client: ToDusClient,
    token: str,
    path: Union[str, Path],
    part_size: int,
    max_retry: int = MAX_RETRY,
) -> str:

    with open(path, "rb") as file:
        data = file.read()

    filename = Path(path).name

    logger.info("Compressing parts ...")

    with TemporaryDirectory() as tempdir:
        with multivolumefile.open(  # type: ignore
            Path(f"{tempdir}/{filename}.7z"),
            "wb",
            volume=part_size,
        ) as vol:
            with py7zr.SevenZipFile(vol, "w") as archive:  # type: ignore
                archive.writestr(data, filename)
        del data
        parts = sorted(_file.name for _file in Path(tempdir).iterdir())
        parts_count = len(parts)

        logger.info(f"Uploading {parts_count} parts ...")

        urls = []

        for i, name in enumerate(parts, 1):
            temp_path = Path(f"{tempdir}/{name}")
            _url = client.upload_file(token, temp_path, i, max_retry)
            if _url:
                urls.append(_url)
            time.sleep(5)

        path = write_txt(filename, urls, parts)
    return path


def get_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=__app_name__,
        description="ToDus Client for S3",
    )
    parser.add_argument(
        "-n",
        "--number",
        dest="number",
        metavar="PHONE-NUMBER",
        help="account's phone number",
        required=True,
    )
    parser.add_argument(
        "-c",
        "--config-folder",
        dest="folder",
        type=str,
        default=".",
        help="folder where account configuration will be saved/loaded",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=__version__,
        help="show program's version number and exit.",
    )

    subparsers = parser.add_subparsers(dest="command")

    _ = subparsers.add_parser(name="login", help="authenticate in server")

    token_arg = ("-k", "--token")
    token_kwarg = dict(
        dest="token", default="", help="use this token for download/upload"
    )

    up_parser = subparsers.add_parser(name="upload", help="upload file")
    up_parser.add_argument(
        "-p",
        "--part-size",
        dest="part_size",
        type=int,
        default=0,
        help="if given, the file will be split in parts of the given size in bytes",
    )
    up_parser.add_argument("file", nargs="+", help="file or directory to upload")
    up_parser.add_argument(*token_arg, **token_kwarg)  # type: ignore[arg-type]

    down_parser = subparsers.add_parser(name="download", help="download file")
    down_parser.add_argument(
        "-t",
        "--max-threads",
        type=int,
        default=MAX_WORKERS,
        metavar="MAX-WORKERS",
        help="Maximum number of concurrent downloads (Default: 3)",
    )
    down_parser.add_argument(*token_arg, **token_kwarg)  # type: ignore[arg-type]
    down_parser.add_argument("url", nargs="+", help="url to download or txt file path")

    return parser


def register(client: ToDusClient, phone: str) -> str:
    client.request_code(phone)
    pin = input("Enter PIN:").strip()
    password = client.validate_code(phone, pin)
    if not password:
        raise RuntimeError("Invalid PIN")
    tqdm_logging(logging.DEBUG, f"PASSWORD: {password}")
    return password


def read_config(phone: str, folder: str = ".") -> ConfigParser:
    config_path = Path(folder) / Path(f"{phone}.ini")
    config.read(config_path)
    return config


def save_config(phone: str, folder: str = ".") -> None:
    with open(Path(folder) / Path(f"{phone}.ini"), "w") as configfile:
        config.write(configfile)


def get_default(dtype, dkey: str, phone: str, folder: str, dvalue: str = ""):
    return dtype(
        read_config(phone, folder)["DEFAULT"].get(dkey, str(dvalue))
        if "DEFAULT" in config
        else dvalue
    )


def _upload(client: ToDusClient, token: str, args: argparse.Namespace, max_retry: int):
    """Upload files and files in directories"""
    files: List[Union[str, Path]] = args.file
    paths = list(
        list(generator)
        for generator in (
            Path(_path).iterdir() for _path in files if Path(_path).is_dir()
        )
    )
    # Flat List
    paths_list: List[Path] = (
        [_path.resolve() for _path in paths[0] if paths[0]] if paths else []
    )

    files = [Path(_path).resolve() for _path in files if Path(_path).is_file()]
    all_paths: List[Union[str, Path]] = files + paths_list  # type: ignore

    for path in all_paths:
        filename = Path(path).name
        logger.info(f"Uploading: {filename}")
        if args.part_size:
            if py7zr is None:
                raise ImportError(
                    "ModuleNotFoundError: No module named 'py7zr'\n"
                    f"Install extra dependency like `pip install {__app_name__}[7z]`"
                )
            txt = split_upload(client, token, path, args.part_size, max_retry=max_retry)
            logger.info(f"TXT: {txt}")
        else:
            filename_path = Path(path)
            file_uri = client.upload_file(token, filename_path, max_retry=max_retry)
            down_url = f"{file_uri}?name={quote_plus(filename)}"
            logger.info(f"URL: {down_url}")
            txt = write_txt(filename, urls=[file_uri], parts=[filename])
            logger.info(f"TXT: {txt}")


def _download(
    client: ToDusClient,
    token: str,
    args: argparse.Namespace,
    down_timeout: float,
    max_retry: int,
    max_workers: int = MAX_WORKERS,
):
    urls = []
    download_tasks = {}

    while args.url:
        file_uri = args.url.pop(0)

        # Extract URLS from current TXT
        if os.path.exists(file_uri):
            with open(file_uri) as fp:
                for line in fp.readlines():
                    line = line.strip()
                    if line:
                        _url, _filename = line.split(maxsplit=1)
                        urls.append(f"{_url}?name={_filename}")

                args.url = urls + args.url
                continue

        if urls:
            count_files = len(urls)
            plural = "" if count_files <= 1 else "s"
            tqdm_logging(logging.DEBUG, f"Downloading: {count_files} file{plural}")

        tqdm_logging(logging.DEBUG, f"Downloading: {file_uri}")

        name = ""
        if "?name=" in file_uri:
            file_uri, name = file_uri.split("?name=", maxsplit=1)
        else:
            raise FileNotFoundError(f"File {file_uri} not found!")

        name = unquote_plus(name)
        download_tasks[name] = (
            token,
            file_uri,
            name,
            down_timeout,
            max_retry,
        )
        urls = []

    tqdm.set_lock(TRLock())
    pool_args: Dict[str, Any] = {}
    if PY3_7:
        pool_args.update(initializer=tqdm.set_lock, initargs=(tqdm.get_lock(),))

    with ThreadPoolExecutor(max_workers=max_workers, **pool_args) as tpe:
        try:
            for v_args in download_tasks.values():
                tpe.submit(client.download_file, *v_args)
                time.sleep(3)  # Rate limit
        except KeyboardInterrupt:
            client.exit = True
            client.session.close()


def main(
    client: ToDusClient = None,
    action: str = "login",
    phone_number: str = "",
    folder_conf: str = ".",
) -> int:
    """Main entrypoint adapted for Notebooks"""
    global config, logger

    if not client:
        client = ToDusClient()

    folder: str = folder_conf
    phone: str = ""
    token: Optional[str] = None
    parser = None
    error_code = ErrorCode.SUCCESS

    if not phone_number:
        parser = get_parser()
        args = parser.parse_args()
        folder = args.folder
        phone = normalize_phone_number(args.number)
        command = args.command
        token = args.token
    else:
        phone = normalize_phone_number(str(phone_number))
        command = action

    password: str = get_default(str, "password", phone, folder, "")
    max_retry: int = get_default(int, "max_retry", phone, folder, str(MAX_RETRY))
    config["DEFAULT"]["max_retry"] = str(max_retry)
    down_timeout: float = get_default(
        float, "down_timeout", phone, folder, str(DOWN_TIMEOUT)
    )
    config["DEFAULT"]["down_timeout"] = str(down_timeout)
    production: bool = get_default(bool, "production", phone, folder, "True")
    config["DEFAULT"]["production"] = str(production)

    if production:
        logging.raiseExceptions = False
    else:
        logger.setLevel(logging.DEBUG)

    if not password and args.command != "login":  # type: ignore
        print("ERROR: account not authenticated, login first.")
        return ErrorCode.MAIN

    if command == "upload":
        if not token:
            token = client.login(phone, password)
        tqdm_logging(logging.DEBUG, f"Token: '{token}'")
        _upload(client, token, args, max_retry)  # type: ignore
    elif command == "download":
        if not token:
            token = client.login(phone, password)
        max_workers: int = args.max_threads  # type: ignore
        tqdm_logging(logging.DEBUG, f"Token: '{token}'")
        _download(client, token, args, down_timeout, max_retry, max_workers)  # type: ignore
    elif command == "login":
        password = register(client, phone)
        token = client.login(phone, password)
        tqdm_logging(logging.DEBUG, f"Token: '{token}'")

        config["DEFAULT"]["password"] = password
        config["DEFAULT"]["token"] = token
    elif parser:
        parser.print_usage()
    else:
        raise RuntimeError("Argument Error")

    error_code = client.error_code
    save_config(phone, folder)
    return error_code
