# License: BSD 3-Clause

set -e

# check status and branch before running the unit tests
before="`git status --porcelain -b`"
before="$before"
# storing current working directory
curr_dir=`pwd`

python unit_tests.py

if [[ "$RUN_FLAKE8" == "true" ]]; then
    pre-commit run --all-files
fi


