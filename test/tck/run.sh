#!/bin/bash
set -ex

rm -rf features
cp -r ../../openCypher/tck/features/ .
mkdir features/steps
cp steps.py features/steps/

export CYPHERCHECK=$(realpath ../../main.py)
behave --stop
