"""Setup module installation."""

import os
import re

from setuptools import find_packages, setup


def get_requirements(file_path):
    with open(file_path, encoding="utf-8") as req:
        requires_deps = [
            line.replace("==", ">=")
            for line in req.read().split("\n")
            if line and not line.startswith(("#", "-"))
        ]
    return requires_deps


if __name__ == "__main__":
    MODULE_NAME = "todus3"
    DESC = "ToDus client"
    URL = "https://github.com/oleksis/todus/tree/todus3"
    version = ""

    with open(os.path.join(MODULE_NAME, "__init__.py"), encoding="utf-8") as fh:
        m = re.search(r"__version__ = \"(.*?)\"", fh.read(), re.M)
        if m:
            version = m.group(1)

    with open("README.md", encoding="utf-8") as fh:
        long_description = fh.read()

    install_requires = get_requirements("requirements/requirements.txt")
    test_deps = get_requirements("requirements/requirements-test.txt")
    dev_deps = get_requirements("requirements/requirements-dev.txt")

    setup(
        name=MODULE_NAME,
        version=version,
        description=DESC,
        long_description=long_description,
        long_description_content_type="text/markdown",
        author="adbenitez",
        author_email="adbenitez@nauta.cu",
        maintainer="Oleksis Fraga",
        maintainer_email="oleksis.fraga@gmail.com",
        url=URL,
        keywords="todus,s3,client",
        license="MPL",
        classifiers=[
            "Development Status :: 4 - Beta",
            "Programming Language :: Python :: 3",
            "License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)",
            "Operating System :: OS Independent",
            "Topic :: Utilities",
        ],
        zip_safe=False,
        include_package_data=True,
        packages=find_packages(),
        install_requires=install_requires,
        extras_require={
            "test": test_deps,
            "dev": dev_deps,
        },
        python_requires=">=3.6.0",
        entry_points={"console_scripts": [f"{MODULE_NAME} = {MODULE_NAME}.main:main"]},
    )
