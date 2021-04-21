import os
import sys
from setuptools import setup


# Raise warnings if system version is not greater than 3.5
if sys.version_info < (3, 6):
    raise ValueError(
        'Unsupported Python version %d.%d.%d found. Pynisher requires Python '
        '3.6 or higher.' % (sys.version_info.major, sys.version_info.minor, sys.version_info.micro)
    )


HERE = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(HERE, 'requirements.txt')) as fp:
    install_reqs = [r.rstrip() for r in fp.readlines()
                    if not r.startswith('#') and not r.startswith('git+')]


with open('README.rst') as fh:
    long_description = fh.read()

setup(
    name='pynisher',
    version="0.6.4",
    packages=['pynisher'],
    install_requires=install_reqs,
    extras_require={
        "test": [
            "pytest",
            "pre-commit",
            "pytest-cov",
            "pytest-forked",
            "flake8-import-order",
            "scikit-learn",
        ],
    },
    author="Stefan Falkner, Christina Hernandez-Wunsch, Samuel Mueller and Matthias Feurer and Francisco Rivera",
    author_email="feurerm@informatik.uni-freiburg.de",
    description="A small Python library to limit the resources used by a function by executing it inside a subprocess.",
    long_description=long_description,
    long_description_content_type='text/markdown',
    include_package_data=False,
    keywords="resources",
    license="MIT",
    url="https://github.com/automl/pynisher",
    classifiers=[
        "License :: OSI Approved :: BSD License",
        "Natural Language :: English",
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ],
    python_requires='>=3.6',
)
