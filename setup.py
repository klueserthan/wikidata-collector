"""Setup script for wikidata_collector package."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="wikidata-collector",
    version="1.0.0",
    author="Your Name",
    author_email="your-email@example.com",
    description="A pure Python library for fetching public figures and institutions from Wikidata",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/klueserthan/wikidata-collector",
    packages=find_packages(exclude=["tests", "tests.*"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=8.0.0",
            "pytest-mock>=3.12.0",
            "pytest-cov>=4.1.0",
        ],
    },
)
