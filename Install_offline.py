# install_offline.py
import os
import subprocess
import shutil
import glob
from pathlib import Path

# Константы
VENv_DIR = Path(".venv")
MODELS_DIR = Path("models")
REQUIREMENTS_FILE = "requirements/requirements.txt"
MODEL_NAME = "intfloat/multilingual-e5-large"
MODEL_TARGET_DIR = Path("models", "multilingual-e5-large")

def create_venv():
    """Создает виртуальное окружение"""
    if VENv_DIR.exists():
        print(f"Удаление существующего виртуального окружения {VENv_DIR}")
        shutil.rmtree(VENv_DIR)
    print(f"Создание нового виртуального окружения в {VENv_DIR}")
    subprocess.run([os.sys.executable, "-m", "venv", str(VENv_DIR)], check=True)

def parse_requirements():
    """Парсит requirements.txt и возвращает список пакетов в порядке установки"""
    packages = []
    with open(REQUIREMENTS_FILE, 'r') as f:
        for line in f:
            line = line.strip()
            # Пропуск комментариев и пустых строк
            if not line or line.startswith('#') or line.startswith('--'):
                continue
            # Остановка после тестовых зависимостей
            if line.startswith('# Тестирование'):
                break
            if '==' in line:
                packages.append(line)
    return packages

def find_wheel(package, models_dir):
    """Находит .whl файл для пакета в директории models_dir"""
    package_name, version = package.split('==', 1)
    # Пытаемся найти соответствующий .whl файл
    patterns = [
        f"{package_name.replace('-', '_').lower()}*{version}*.whl",
        f"{package_name.replace('_', '-').lower()}*{version}*.whl"
    ]
    
    for pattern in patterns:
        wheel_files = glob.glob(str(models_dir / pattern))
        if wheel_files:
            return wheel_files[0]
    
    raise FileNotFoundError(f"Не найден .whl файл для {package}")

def install_packages(packages, models_dir, pip_path):
    """Устанавливает пакеты в виртуальное окружение"""
    for package in packages:
        try:
            wheel_file = find_wheel(package, models_dir)
            print(f"Установка {package} из {wheel_file}")
            subprocess.run([
                pip_path, "install", "--no-index", "--find-links", str(models_dir),
                str(wheel_file)
            ], check=True)
        except Exception as e:
            print(f"Ошибка при установке {package}: {e}")
            raise

def install_model(models_dir):
    """Копирует модель в целевую директорию"""
    model_source = models_dir / MODEL_NAME.split("/")[1]
    if model_source.exists():
        print(f"Копирование модели {MODEL_NAME} в {MODEL_TARGET_DIR}")
        if MODEL_TARGET_DIR.exists():
            shutil.rmtree(MODEL_TARGET_DIR)
        shutil.copytree(model_source, MODEL_TARGET_DIR)
    else:
        raise FileNotFoundError(f"Модель {MODEL_NAME} не найдена в {models_dir}")

def main():
    # Создаем виртуальное окружение
    create_venv()

    # Получаем путь к pip в виртуальном окружении
    if os.name == 'nt':
        pip_path = VENv_DIR / "Scripts" / "pip.exe"
    else:
        pip_path = VENv_DIR / "bin" / "pip"

    # Проверяем существование директории с пакетами
    if not MODELS_DIR.exists():
        raise FileNotFoundError(f"Директория {MODELS_DIR} не найдена")

    # Парсим требования
    packages = parse_requirements()
    print(f"Найдено {len(packages)} пакетов для установки")

    # Устанавливаем пакеты
    install_packages(packages, MODELS_DIR, pip_path)

    # Устанавливаем модель
    install_model(MODELS_DIR)

    print("Установка завершена успешно")

if __name__ == "__main__":
    main()