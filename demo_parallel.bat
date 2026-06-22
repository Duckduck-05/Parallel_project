@echo off
REM One-click "islands race" parallelism demo (Windows + WSL).
REM   1) runs the C++ MPI solver in WSL with --out, so EVERY rank writes its own
REM      convergence history (results/race.rankN.history) - no extra MPI communication
REM   2) opens the native viewer that overlays all islands' curves + the global best,
REM      with vertical markers at each sync -> you watch the islands search in parallel
REM      and share results.
REM Requirements: WSL with OpenMPI 5.0.9 in /opt; Windows `python` with numpy + matplotlib.
setlocal
set "REPO=%~dp0"
set "REPO=%REPO:~0,-1%"
for /f "delims=" %%i in ('wsl wslpath "%REPO%"') do set "WREPO=%%i"

echo [1/2] Running 4-island solver in WSL (per-rank histories)...
wsl bash -lc "export PATH=/opt/openmpi-5.0.9/bin:$PATH; export LD_LIBRARY_PATH=/opt/openmpi-5.0.9/lib; cd '%WREPO%' && { [ -x cpp/tsp_island ] || make -C cpp tsp_island CXX=/opt/openmpi-5.0.9/bin/mpicxx; } && mpirun --oversubscribe -np 4 ./cpp/tsp_island data/cities_500.txt --gens 2000 --sync 100 --migrants 2 --seed 7 --out results/race"
if errorlevel 1 ( echo Solver failed - check WSL / OpenMPI. & pause & exit /b 1 )

echo [2/2] Opening the islands-race viewer...
python "%REPO%\python\live_view.py" race "%REPO%\results\race" --sync 100 --step 8 --interval 60
endlocal
