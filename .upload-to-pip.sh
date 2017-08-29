#!/usr/bin/env bash
if [[ `git describe` == `python setup.py --version` && `git describe` == *-* ]]; then
else
  pip install twine
  rm -rf build dist
  python setup.py sdist bdist_wheel
  twine upload dist/*
fi