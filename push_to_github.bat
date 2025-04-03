@echo off
cd /d %~dp0

:: Получить дату для логов и тегов
for /f %%i in ('powershell -Command "Get-Date -Format yyyy-MM-dd_HH-mm"') do set now=%%i

:: Ввод кастомного сообщения
set /p msg=Enter commit message:
if "%msg%"=="" set msg=feat: auto push at %now%

:: Добавление изменений
echo [BOT] 🗂 Adding all changes...
git add .

:: Коммит
echo [BOT] 📝 Committing with message: %msg%
git commit -m "%msg%" >nul 2>&1

IF %ERRORLEVEL% EQU 1 (
    echo [BOT] ⚠️ Nothing to commit.
) ELSE (
    echo [BOT] ✅ Commit done with message: %msg%
)

:: Пуш в основную ветку
echo [BOT] 📤 Pushing to GitHub...
git push origin main

IF %ERRORLEVEL% EQU 0 (
    echo [BOT] ✅ Code pushed successfully!

    :: Добавляем git tag по дате и пушим его
    git tag v%now%
    git push origin v%now%

    :: Логирование результата в файл
    echo [%now%] ✅ Pushed with message: %msg% >> push_log.txt

) ELSE (
    echo [BOT] ❌ Push failed. Check connection or authentication.
    echo [%now%] ❌ Push failed with message: %msg% >> push_log.txt
)

pause
