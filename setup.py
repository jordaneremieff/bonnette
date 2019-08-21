import re
import os
from setuptools import find_packages, setup


def get_long_description():
    return open("README.md", "r", encoding="utf8").read()


def get_version(package):
    with open(os.path.join(package, "__version__.py")) as f:
        return re.search("__version__ = ['\"]([^'\"]+)['\"]", f.read()).group(1)


setup(
    name="bonnette",
    version=get_version("bonnette"),
    packages=find_packages(),
    license="MIT",
    url="https://github.com/erm/bonnette",
    description="ASGI adapter for Azure Functions",
    long_description=get_long_description(),
    install_requires=["azure-functions"],
    package_data={"bonnette": ["py.typed"]},
    long_description_content_type="text/markdown",
    author="Jordan Eremieff",
    author_email="jordan@eremieff.com",
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
    ],
)
