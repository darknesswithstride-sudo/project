@echo off
setlocal
if "%UE_ROOT%"=="" (echo Set UE_ROOT to Unreal Engine installation folder & exit /b 2)
set UPROJECT=%~dp0..\quality.uproject
"%UE_ROOT%\Engine\Build\BatchFiles\Build.bat" qualityEditor Win64 Development "%UPROJECT%" -WaitMutex -FromMsBuild
if errorlevel 1 exit /b %errorlevel%
"%UE_ROOT%\Engine\Build\BatchFiles\RunUAT.bat" BuildCookRun -project="%UPROJECT%" -noP4 -platform=Win64 -clientconfig=Development -build -cook -stage -pak -archive -archivedirectory="%~dp0..\Build\Win64"
if errorlevel 1 exit /b %errorlevel%
python "%~dp0Write-Package-Manifest.py"
exit /b %errorlevel%
