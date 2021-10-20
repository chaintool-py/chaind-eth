#!/bin/bash

set -e
set -x
set -a
export PYTHONPATH=${PYTHONPATH:.}
for f in `ls tests/*.py`; do
	python $f
done
set +a
set +x
set +e
