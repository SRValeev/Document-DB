@echo off
setlocal enabledelayedexpansion

REM ------ Конфигурация ------
set PYTHON_VERSION=3.12
set PROJECT_NAME=RAGDocumentAssistant
set DIST_DIR=dist_offline
set VENV_NAME=venv_dist

REM ------ Очистка предыдущей сборки ------
if exist "%DIST_DIR%" rmdir /s /q "%DIST_DIR%"
mkdir "%DIST_DIR%"

REM ------ Создание виртуального окружения ------
python -m venv "%VENV_NAME%"
call "%VENV_NAME%\Scripts\activate.bat"

REM ------ Установка базовых зависимостей ------
pip install --upgrade pip
pip install wheel setuptools

REM ------ Скачивание моделей ------
REM SpaCy модель (ru_core_news_lg)
pip download ru_core_news_lg -d "%DIST_DIR%\models"
python -m spacy download ru_core_news_lg --direct --download-dir "%DIST_DIR%\models"

REM Sentence Transformers модель (multilingual-e5-large)
pip download sentence-transformers -d "%DIST_DIR%\models"
mkdir "%DIST_DIR%\models\multilingual-e5-large"
python -c "from sentence_transformers import SentenceTransformer; model = SentenceTransformer('intfloat/multilingual-e5-large'); model.save('%DIST_DIR%\models\multilingual-e5-large')"

REM ------ Сборка зависимостей ------
pip download -r requirements\requirements.txt -d "%DIST_DIR%\dependencies"

REM ------ Копирование исходного кода ------
xcopy /E /I /Y src "%DIST_DIR%\src"
xcopy /E /I /Y config.yaml "%DIST_DIR%\"
xcopy /E /I /Y requirements\requirements.txt "%DIST_DIR%\"
xcopy /E /I /Y spacy_models.txt "%DIST_DIR%\"

REM ------ Создание скриптов установки ------
REM install.bat
echo @echo off > "%DIST_DIR%\install.bat"
echo setlocal enabledelayedexpansion >> "%DIST_DIR%\install.bat"
echo set PYTHON_VERSION=%PYTHON_VERSION% >> "%DIST_DIR%\install.bat"
echo set PROJECT_NAME=%PROJECT_NAME% >> "%DIST_DIR%\install.bat"
echo echo Создание виртуального окружения... >> "%DIST_DIR%\install.bat"
echo python -m venv venv >> "%DIST_DIR%\install.bat"
echo call venv\Scripts\activate.bat >> "%DIST_DIR%\install.bat"
echo echo Установка зависимостей... >> "%DIST_DIR%\install.bat"
echo pip install --no-index --find-links=dependencies -r requirements\requirements.txt >> "%DIST_DIR%\install.bat"
echo echo Установка моделей SpaCy... >> "%DIST_DIR%\install.bat"
echo pip install --no-index --find-links=models ru_core_news_lg-*.whl >> "%DIST_DIR%\install.bat"
echo python -m spacy link --force models\ru_core_news_lg ru_core_news_lg >> "%DIST_DIR%\install.bat"
echo echo Копирование модели multilingual-e5-large... >> "%DIST_DIR%\install.bat"
echo xcopy /E /I /Y models\multilingual-e5-large .\model_cache\ /Y >> "%DIST_DIR%\install.bat"
echo echo Установка завершена! >> "%DIST_DIR%\install.bat"
echo pause >> "%DIST_DIR%\install.bat"

REM service_install.bat
echo @echo off > "%DIST_DIR%\service_install.bat"
echo set SERVICE_NAME=%PROJECT_NAME%_Service >> "%DIST_DIR%\service_install.bat"
echo set APP_PATH=%~dp0startup.bat >> "%DIST_DIR%\service_install.bat"
echo echo Установка службы Windows... >> "%DIST_DIR%\service_install.bat"
echo nssm install "%SERVICE_NAME%" "%APP_PATH%" >> "%DIST_DIR%\service_install.bat"
echo nssm set "%SERVICE_NAME%" AppDirectory "%~dp0" >> "%DIST_DIR%\service_install.bat"
echo nssm set "%SERVICE_NAME%" AppStdout "%~dp0app.log" >> "%DIST_DIR%\service_install.bat"
echo nssm set "%SERVICE_NAME%" AppStderr "%~dp0app_error.log" >> "%DIST_DIR%\service_install.bat"
echo nssm set "%SERVICE_NAME%" Start SERVICE_DELAYED_AUTO_START >> "%DIST_DIR%\service_install.bat"
echo echo Служба установлена. Запуск: nssm start %SERVICE_NAME% >> "%DIST_DIR%\service_install.bat"
echo pause >> "%DIST_DIR%\service_install.bat"

REM startup.bat
echo @echo off > "%DIST_DIR%\startup.bat"
echo call venv\Scripts\activate.bat >> "%DIST_DIR%\startup.bat"
echo set PYTORCH_OFFLINE=1 >> "%DIST_DIR%\startup.bat"
echo set TRANSFORMERS_OFFLINE=1 >> "%DIST_DIR%\startup.bat"
echo python -m src.main >> "%DIST_DIR%\startup.bat"

REM ------ Упаковка в ZIP ------
powershell Compress-Archive -Path "%DIST_DIR%\*" -DestinationPath "%PROJECT_NAME%_Offline_Dist.zip"

echo Дистрибутив собран: %PROJECT_NAME%_Offline_Dist.zip
pause