#!/usr/bin/env bash
# License: BSD 3-Clause

set -e

# Deactivate the travis-provided virtual environment and setup a
# conda-based environment instead
deactivate

# Use the miniconda installer for faster download / install of conda
# itself
pushd .
cd
mkdir -p download
cd download
echo "Cached in $HOME/download :"
ls -l
echo
if [[ ! -f miniconda.sh ]]
   then
   wget https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh \
       -O miniconda.sh
   fi
chmod +x miniconda.sh && ./miniconda.sh -b -p $HOME/miniconda
cd ..
export PATH=/home/travis/miniconda/bin:$PATH
conda update --yes conda
popd

# Configure the conda environment and put it in the path using the
# provided versions
conda create -n testenv --yes python=$PYTHON_VERSION pip
source activate testenv

if [[ -v SCIPY_VERSION ]]; then
    conda install --yes scipy=$SCIPY_VERSION
fi
python --version

if [[ "$TEST_DIST" == "true" ]]; then
    pip install twine nbconvert jupyter_client matplotlib pyarrow pytest pytest-xdist pytest-timeout \
        nbformat oslo.concurrency flaky
    python setup.py sdist
    # Find file which was modified last as done in https://stackoverflow.com/a/4561987
    dist=`find dist -type f -printf '%T@ %p\n' | sort -n | tail -1 | cut -f2- -d" "`
    echo "Installing $dist"
    pip install "$dist"
    twine check "$dist"
else
    pip install -e '.[test]'
fi

#pip install codecov pytest-cov
pip install pre-commit
pre-commit install

pip install pep8 codecov mypy flake8 pytest-cov flake8-import-order
pip install -r requirements.txt

conda list
