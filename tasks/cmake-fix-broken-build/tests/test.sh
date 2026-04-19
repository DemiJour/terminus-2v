#!/bin/bash

python3 -m pip install --break-system-packages "uv==0.6.12" "pytest==8.3.5"
uvx --with pytest==8.3.5 pytest /tests/test_outputs.py -v -rA

if [ $? -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
