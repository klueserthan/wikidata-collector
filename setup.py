"""Setup script for wikidata_collector package."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

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
        "Programming Language :: Python :: 3.13",
    ],
    python_requires=">=3.13",
    install_requires=[
        "pydantic>=2.12.3",
        "pytest>=8.0.0",
        "pytest-cov>=4.1.0",
        "pytest-mock>=3.12.0",
        "python-dotenv>=1.1.1",
        "requests>=2.32.5",
    ],
    extras_require={
        "dev": [
            "pytest>=8.0.0",
            "pytest-mock>=3.12.0",
            "pytest-cov>=4.1.0",
            "ruff>=0.14.9",
            "pyright>=1.1.390",
        ],
    },
)
