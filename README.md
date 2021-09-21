# ToDus client for S3

[![](https://img.shields.io/pypi/v/todus3.svg)](https://pypi.org/project/todus3)
[![](https://img.shields.io/pypi/pyversions/todus3.svg)](
https://pypi.org/project/todus3)
[![Downloads](https://pepy.tech/badge/todus3)](https://pepy.tech/project/todus3)
[![](https://img.shields.io/pypi/l/todus3.svg)](https://pypi.org/project/todus3)
[![CI](https://github.com/oleksis/todus/actions/workflows/python-ci.yml/badge.svg)](https://github.com/oleksis/todus/actions/workflows/python-ci.yml)
[![](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Use the ToDus API (**login/download/upload**) in your Python projects.

📦 The package is adapted for [use in Jupyter Notebook](https://github.com/oleksis/todus/blob/todus3/docs/todus3.ipynb) 📓

## Install

To install run:
```bash
  pip install todus3
```

If want support for upload by parts using 7Zip (py7zr):
```bash
  pip install todus3[7z]
```

## Usage
```bash
### Help
todus3 -- help

### Login and Enter PIN
todus3 -n 53123456 login

### Download from TXT files with 3 Workers/Threads
todus3 -n 53123456 download -t 3 file.txt [file.txt ...]

### Upload file by parts in Bytes (10 MB)
todus3 -n 53123456 upload binary.bin -p 10485760
```

## Configuration

When using `todus3` the configuration file (.ini) is created with the `DEFAULT` section and the following keys with values:

```
[DEFAULT]
max_retry = 3  # Maximum number of times to repeat if an error occurs
down_timeout = 30.0  # Maximum time in seconds to reach time out
production = True
password = PASSWORD  # Password established when sending the registration code
token = TOKEN  # Token that is used in the authentication for uploading or downloading files
```

## ⚠ Advice

The following is recommended for uploading or downloading the file:

If your speed (download/upload) is equal to 70 KB/s in 120 seconds (ToDus limit) you can upload up to approximately 8 MB

* P (Part of the file in MB)
* Vd (Average download speed in KB/s)

```
P = Vd * 120 / 1024
```

## Developmet 
For execute app in development mode you need install [poetry](https://python-poetry.org/) or use [Docker](## Docker)
Install dependencies 
```shell
poetry config virtualenvs.create false && poetry install --no-interaction --no-ansi
```

Run app with *poetry run*, for example:
```shell
poetry run todus3 -n 58963247 login
```

## Docker
### Previous requirements
* [Install Docker](https://docs.docker.com/engine/install/) in your system
* [Install Docker Compose](https://docs.docker.com/compose/install/) in your system

### Use for development
Build image
```shell
docker-compose build
```

Run image
```shell
docker-compose up -d
```

Run command in container
```shell
docker-compose exec app bash
```


## Contributing
Follow the [dev branch](https://github.com/oleksis/todus/tree/todus3) and [Feedbacks](https://github.com/oleksis/todus/issues) or [Pull Requests](https://github.com/oleksis/todus/pulls) are welcome 🙏🏾
