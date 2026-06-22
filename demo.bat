@echo off
REM One-click interactive demo (Windows + WSL).
REM   1) builds (if needed) and runs the C++ MPI solver in WSL, streaming --live
REM   2) opens the native matplotlib viewer that REPLAYS the search from generation 1
REM Requirements: WSL with OpenMPI 5.0.9 in /opt; Windows `python` with numpy + matplotlib
REM (pip install -r requirements.txt). Edit N / gens / flags below to taste.
setlocal
set "REPO=%~dp0"
set "REPO=%REPO:~0,-1%"
for /f "delims=" %%i in ('wsl wslpath "%REPO%"') do set "WREPO=%%i"

echo [1/2] Building (if needed) + running solver in WSL, streaming live...
wsl bash -lc "export PATH=/opt/openmpi-5.0.9/bin:$PATH; export LD_LIBRARY_PATH=/opt/openmpi-5.0.9/lib; cd '%WREPO%' && { [ -x cpp/tsp_island ] || make -C cpp tsp_island CXX=/opt/openmpi-5.0.9/bin/mpicxx; } && mpirun --oversubscribe -np 4 ./cpp/tsp_island data/cities_1000.txt --gens 2000 --sync 25 --twoopt 20 --migrants 3 --seed 7 --live results/stream.jsonl"
if errorlevel 1 ( echo Solver failed - check WSL / OpenMPI. & pause & exit /b 1 )

echo [2/2] Opening interactive viewer (replays the search)...
python "%REPO%\python\live_view.py" tail "%REPO%\results\stream.jsonl" "%REPO%\data\cities_1000.txt" --interval 60 --step 4
endlocal
