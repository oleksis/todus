# ToDus client for S3

[![](https://img.shields.io/pypi/v/todus3.svg)](https://pypi.org/project/todus3)
[![](https://img.shields.io/pypi/pyversions/todus3.svg)](
https://pypi.org/project/todus3)
[![](https://img.shields.io/pypi/l/todus3.svg)](https://pypi.org/project/todus3)
[![CI](https://github.com/oleksis/todus/actions/workflows/python-ci.yml/badge.svg)](https://github.com/oleksis/todus/actions/workflows/python-ci.yml)
[![](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Use the ToDus API in your Python projects.

## Install

To install run::
```bash
  pip install todus3
```

## Usage
```bash
todus3 -- help

todus3 -n 53123456 login

todus3 -n 53123456 download file.txt

todus3 -n 53123456 upload binary.zip -p 10485760
```
