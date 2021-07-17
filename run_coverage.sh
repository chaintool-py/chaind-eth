#!/bin/bash

#set -e
#set -x
#export PYTHONPATH=${PYTHONPATH:.}
#for f in `ls tests/*.py`; do
#	python $f
#done
#set +x
#set +e
COVERAGE_MINIMUM=${COVERAGE_MINIMUM:-90}
coverage run -m unittest tests/test_*.py
coverage report -m --fail-under $COVERAGE_MINIMUM
