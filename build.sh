#!/bin/bash
# Windows build via Wine: PyInstaller onedir + Inno Setup per-user installer + onefile portable + zip
set -e
export WINEPREFIX=/workspace/exwifi/.wine WINEDEBUG=-all
cd "$(dirname "$0")"
V=$(grep -oP '^VERSION = "\K[^"]+' miyoyazu_dash.py)
PY='C:\Python311\python.exe'
wine "$PY" -m PyInstaller --noconfirm "MIYOYAZU DASH.spec" > build_dir.log 2>&1; echo DIR_DONE
wine "C:\\InnoSetup\\ISCC.exe" installer.iss > build_iss.log 2>&1; echo ISS_DONE
wine "$PY" -m PyInstaller --noconfirm --workpath build_onefile --distpath dist_onefile "MIYOYAZU DASH onefile.spec" > build_1f.log 2>&1
cp "dist_onefile/MIYOYAZU DASH.exe" dist/MIYOYAZU-DASH-Portable.exe; echo ONEFILE_DONE
cd dist && rm -f MIYOYAZU-DASH-$V-Windows-x64.zip && python3 -c "import shutil; shutil.make_archive('MIYOYAZU-DASH-$V-Windows-x64', 'zip', '.', 'MIYOYAZU DASH')" && echo ZIP_DONE
ls -la
