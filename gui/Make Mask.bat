@echo off
rem Double-click this to open the mask window. Needs Python 3 from python.org.
start "" pythonw "%~dp0mask_gui.py"
if errorlevel 1 (
  echo Could not start Python. Install Python 3 from https://python.org and tick
  echo "Add python.exe to PATH" during setup, then try again.
  pause
)
