@echo off
if "%UE_ROOT%"=="" (echo Set UE_ROOT to your Unreal Engine installation folder first. & exit /b 2)
"%UE_ROOT%\Engine\Build\BatchFiles\Build.bat" qualityEditor Win64 Development "%~dp0..\quality.uproject" -WaitMutex -FromMsBuild
if errorlevel 1 exit /b %errorlevel%
echo Build succeeded. Package from Unreal Editor: Platforms ^> Windows ^> Package Project.
pause
