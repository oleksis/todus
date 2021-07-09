import argparse
import configparser
import logging
import os
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import quote_plus, unquote_plus

import multivolumefile
import py7zr

from . import __version__
from .client import ToDusClient

logging.basicConfig(format="%(levelname)s - %(message)s", level=logging.INFO)


client = ToDusClient()
config = configparser.ConfigParser()


def split_upload(token: str, path: str, part_size: int) -> str:
    global client

    with open(path, "rb") as file:
        data = file.read()
    filename = os.path.basename(path)
    with TemporaryDirectory() as tempdir:
        with multivolumefile.open(
            os.path.join(tempdir, filename + ".7z"),
            "wb",
            volume=part_size,
        ) as vol:
            with py7zr.SevenZipFile(vol, "w") as a:  # type: ignore
                a.writestr(data, filename)
        del data
        parts = sorted(os.listdir(tempdir))
        parts_count = len(parts)

        urls = []

        for i, name in enumerate(parts, 1):
            logging.info(f"Uploading {i}/{parts_count}: {filename}")
            with open(os.path.join(tempdir, name), "rb") as file:
                part = file.read()
            try:
                urls.append(client.upload_file(token, part, len(part)))
            except Exception as ex:
                logging.exception(ex)
                time.sleep(15)
                try:
                    urls.append(client.upload_file(token, part, len(part)))
                except Exception as ex:
                    logging.exception(ex)
                    raise ValueError(
                        f"Failed to upload part {i} ({len(part):,}B): {ex}"
                    )

        txt = "\n".join(f"{down_url}\t{name}" for down_url, name in zip(urls, parts))
        path = os.path.abspath(filename + ".txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(txt)
        return path


def get_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=__name__.split(".")[0],
        description="ToDus Client",
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
    logging.debug("PASSWORD: %s", password)
    return password


def get_password(phone: str, folder: str) -> str:
    config_path = Path(folder) / Path(f"{phone}.ini")
    config.read(config_path)
    return config["DEFAULT"].get("password", "") if "DEFAULT" in config else ""


def save_config(phone: str, folder: str = ".") -> None:
    with open(Path(folder) / Path(f"{phone}.ini"), "w") as configfile:
        config.write(configfile)


def main() -> None:
    global client

    parser = get_parser()
    args = parser.parse_args()
    phone = args.number
    password = get_password(phone, args.folder) or "***FIX_TEMP***"

    if not password and args.command != "login":
        print("ERROR: account not authenticated, login first.")
        return

    if args.command == "upload":
        # token = client.login(phone, password)
        token = config["DEFAULT"].get("token", "") if "DEFAULT" in config else ""
        logging.debug(f"Token: '{token}'")

        for path in args.file:
            logging.info(f"Uploading: {path}")
            if args.part_size:
                txt = split_upload(token, path, args.part_size)
                logging.info(f"TXT: {txt}")
            else:
                with open(path, "rb") as file:
                    data = file.read()
                url = client.upload_file(token, data, len(data))
                url += f"?name={quote_plus(os.path.basename(path))}"
                logging.info(f"URL: {url}")
    elif args.command == "download":
        # token = client.login(phone, password)
        token = config["DEFAULT"].get("token", "") if "DEFAULT" in config else ""
        logging.debug(f"Token: '{token}'")

        while args.url:
            url = args.url.pop(0)
            if os.path.exists(url):
                with open(url) as fp:
                    urls = []
                    for line in fp.readlines():
                        line = line.strip()
                        if line:
                            urls.append("{}?name={}".format(*line.split(maxsplit=1)))

                    args.url = urls + args.url
                    continue
            logging.info(
                f"Downloading: {url}",
            )
            url, name = url.split("?name=", maxsplit=1)
            name = unquote_plus(name)
            try:
                size = client.download_file(token, url, name)
            except Exception:
                size = client.download_file(token, url, name)
            logging.debug(
                f"File Size: {size // 1024}",
            )
    elif args.command == "login":
        # TODO: Fix Register
        # password = register(client, phone)
        # token = client.login(phone, password)

        token = config["DEFAULT"].get("token", "") if "DEFAULT" in config else ""
        logging.debug(f"Token: '{token}'")

        config["DEFAULT"]["password"] = password
        config["DEFAULT"]["token"] = token
        save_config(phone, args.folder)
    else:
        parser.print_usage()
