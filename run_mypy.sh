#!/bin/bash

mypy -p jsonmodels
mypy tests/test_fields.py
