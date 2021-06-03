#!/bin/bash

>&2 echo "waiting for socket at $@ to become ready"
while ! test -S $@; do
	sleep 1s
done
