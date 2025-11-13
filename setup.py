"""
Setup configuration for Seigr Toolset Transmissions (STT).
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read the README file
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding='utf-8')

setup(
    name="seigr-toolset-transmissions",
    version="0.1.0",
    author="Seigr Development Team",
    author_email="dev@seigr.net",
    description="Binary encrypted transmission protocol for the Seigr Ecosystem",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/seigr/seigr-toolset-transmissions",
    packages=find_packages(exclude=["tests", "tests.*", "cli", "docs"]),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: System :: Networking",
        "Topic :: Security :: Cryptography",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.9",
    install_requires=[
        "seigr-toolset-crypto>=0.1.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.0.0",
        ],
        "websocket": [
            "websockets>=11.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "stt-node=cli.node_cli:main",
            "stt-bridge=cli.bridge_cli:main",
        ],
    },
    package_data={
        "seigr_toolset_transmissions": ["py.typed"],
    },
    zip_safe=False,
)
