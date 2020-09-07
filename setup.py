from setuptools import setup

setup(
    name='pynisher',
    version="0.6.0",
    packages=['pynisher'],
    install_requires=['docutils>=0.3', 'setuptools', 'psutil'],
    author="Stefan Falkner, Christina Hernandez-Wunsch, Samuel Mueller and Matthias Feurer",
    author_email="feurerm@informatik.uni-freiburg.de",
    description="A small Python library to limit the resources used by a function by executing it inside a subprocess.",
    include_package_data=False,
    keywords="resources",
    license="MIT",
    url="https://github.com/automl/pynisher",
)
