#!/bin/bash
cd /workspace/miyoyazu-dash
export DISPLAY=:55
rm -f ~/.miyoyazu-dash/md_log.txt
env MD_NOAUDIO=1 MD_TEST=$1 MD_AT=$2 MD_END=$3 MD_SHOTS=/workspace/miyoyazu-dash/shots $4 \
  timeout 180 /workspace/.venv-dv/bin/python miyoyazu_dash.py 2>&1 | grep -v "device\|XFree\|pipe types\|glxGraphicsPipe\|aux display" | tail -30
cat ~/.miyoyazu-dash/md_log.txt 2>/dev/null | tail -20
