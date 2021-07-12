import argparse
import logging
import os
import time
from configparser import ConfigParser
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import List
from urllib.parse import quote_plus, unquote_plus

import multivolumefile
import py7zr

from . import __app_name__, __version__
from .client import ToDusClient

logging.basicConfig(
    format="%(asctime)s-%(levelname)s-%(name)s-%(message)s", level=logging.INFO
)
logger = logging.getLogger(__app_name__)
logger.setLevel(logging.INFO)
handler_error = logging.FileHandler("logs", encoding="utf-8")
handler_error.setLevel(logging.ERROR)
logger.addHandler(handler_error)

client = ToDusClient()
config = ConfigParser()
MAX_RETRY = 3
DOWN_TIMEOUT = 60 * 20  # 20 MINS


def write_txt(filename: str, urls: List[str], parts: List[str]) -> str:
    txt = "\n".join(f"{down_url}\t{name}" for down_url, name in zip(urls, parts))
    path = Path(f"{filename}.txt").resolve()
    with open(path, "w", encoding="utf-8") as f:
        f.write(txt)
    return str(path)


def split_upload(
    token: str, path: str, part_size: int, max_retry: int = MAX_RETRY
) -> str:
    global client

    with open(path, "rb") as file:
        data = file.read()
    filename = Path(path).name
    with TemporaryDirectory() as tempdir:
        with multivolumefile.open(
            Path(f"{tempdir}/{filename}.7z"),
            "wb",
            volume=part_size,
        ) as vol:
            with py7zr.SevenZipFile(vol, "w") as a:  # type: ignore
                a.writestr(data, filename)
        del data
        parts = sorted(_file.name for _file in Path(tempdir).iterdir())
        parts_count = len(parts)

        urls = []

        for i, name in enumerate(parts, 1):
            retry = 0
            up_done = False
            logger.info(f"Uploading {i}/{parts_count}: {name}")
            with open(Path(f"{tempdir}/{name}"), "rb") as file:
                part = file.read()

            while not up_done and retry < max_retry:
                try:
                    urls.append(client.upload_file(token, part, len(part)))
                except Exception as ex:
                    logger.exception(ex)
                    retry += 1
                    if retry == max_retry:
                        raise ValueError(
                            f"Failed to upload part {i} ({len(part):,}B): {ex}"
                        )
                    logger.info(f"Retrying: {retry}...")
                    time.sleep(15)
                else:
                    up_done = True

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

    login_parser = subparsers.add_parser(name="login", help="authenticate in server")

    up_parser = subparsers.add_parser(name="upload", help="upload file")
    up_parser.add_argument(
        "-p",
        "--part-size",
        dest="part_size",
        type=int,
        default=0,
        help="if given, the file will be split in parts of the given size in bytes",
    )
    up_parser.add_argument("file", nargs="+", help="file to upload")

    down_parser = subparsers.add_parser(name="download", help="download file")
    down_parser.add_argument("url", nargs="+", help="url to download or txt file path")

    return parser


def register(client: ToDusClient, phone: str) -> str:
    client.request_code(phone)
    pin = input("Enter PIN:").strip()
    password = client.validate_code(phone, pin)
    logger.debug("PASSWORD: %s", password)
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


def main() -> None:
    global client, config, logger

    parser = get_parser()
    args = parser.parse_args()
    folder: str = args.folder
    phone: str = f"535{args.number[-7:]}"  # Country Code + phone
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

    if not password and args.command != "login":
        print("ERROR: account not authenticated, login first.")
        return

    if args.command == "upload":
        token = client.login(phone, password)
        logger.debug(f"Token: '{token}'")

        for path in args.file:
            filename = Path(path).name
            logger.info(f"Uploading: {filename}")
            if args.part_size:
                txt = split_upload(token, path, args.part_size, max_retry=max_retry)
                logger.info(f"TXT: {txt}")
            else:
                with open(path, "rb") as file:
                    data = file.read()
                file_uri = client.upload_file(token, data, len(data))
                down_url = f"{file_uri}?name={quote_plus(filename)}"
                logger.info(f"URL: {down_url}")
                txt = write_txt(filename, urls=[file_uri], parts=[filename])
                logger.info(f"TXT: {txt}")
    elif args.command == "download":
        token = client.login(phone, password)
        logger.debug(f"Token: '{token}'")

        while args.url:
            retry = 0
            down_done = False
            file_uri = args.url.pop(0)

            if os.path.exists(file_uri):
                with open(file_uri) as fp:
                    urls = []
                    for line in fp.readlines():
                        line = line.strip()
                        if line:
                            _url, _filename = line.split(maxsplit=1)
                            urls.append(f"{_url}?name={_filename}")

                    args.url = urls + args.url
                    continue

            logger.info(
                f"Downloading: {file_uri}",
            )
            file_uri, name = file_uri.split("?name=", maxsplit=1)
            name = unquote_plus(name)
            size = 0

            while not down_done and retry < max_retry:
                try:
                    size = client.download_file(token, file_uri, name, down_timeout)
                except Exception as ex:
                    logger.exception(ex)
                    retry += 1
                    if retry == max_retry:
                        continue
                    logger.info(f"Retrying: {retry}...")
                    time.sleep(15)
                else:
                    down_done = True

            logger.debug(
                f"File Size: {size // 1024}",
            )
    elif args.command == "login":
        password = register(client, phone)
        token = client.login(phone, password)
        logger.debug(f"Token: '{token}'")

        config["DEFAULT"]["password"] = password
        config["DEFAULT"]["token"] = token
    else:
        parser.print_usage()

    save_config(phone, folder)
