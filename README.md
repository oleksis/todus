# ToDus client for S3

[![](https://img.shields.io/pypi/v/todus3.svg)](https://pypi.org/project/todus3)
[![](https://img.shields.io/pypi/pyversions/todus3.svg)](
https://pypi.org/project/todus3)
[![Downloads](https://pepy.tech/badge/todus3)](https://pepy.tech/project/todus3)
[![](https://img.shields.io/pypi/l/todus3.svg)](https://pypi.org/project/todus3)
[![CI](https://github.com/oleksis/todus/actions/workflows/python-ci.yml/badge.svg)](https://github.com/oleksis/todus/actions/workflows/python-ci.yml)
[![](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Use the ToDus API (login/download/upload) in your Python projects.

## Install

To install run
```bash
  pip install todus3
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
