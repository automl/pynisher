from pathlib import Path

from setuptools import setup, find_packages

readme = Path(__file__).parent / "README.md"

with readme.open("r") as fh:
    long_description = fh.read()

setup(
    name="pynisher",
    version="0.7.0",
    packages=find_packages(where=".", include=["pynisher*"], exclude=["test*"]),
    include_package_data=True,
    install_requires=["psutil"],
    extras_require={
        "test": [
            "pytest",
            "pre-commit",
            "pytest-cov",
            "pytest-forked",
            "pydocstyle[toml]",
            "isort",
            "black",
            "flake8",
            "mypy",
            "scikit-learn",
        ],
        "docs": "sphinx",
    },
    author=(
        "Stefan Falkner, Christina Hernandez-Wunsch, Samuel Mueller,"
        "Matthias Feurer, Francisco Rivera, Eddie Bergman and Rene Sass",
    ),
    author_email="feurerm@informatik.uni-freiburg.de",
    description="A library to limit the resources used by functions using subprocesses",
    long_description=long_description,
    long_description_content_type="text/markdown",
    keywords="resources",
    license="MIT",
    url="https://github.com/automl/pynisher",
    classifiers=[
        "License :: OSI Approved :: BSD License",
        "Natural Language :: English",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
    python_requires=">=3.7",
)
