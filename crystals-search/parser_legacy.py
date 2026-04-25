import sys
from pathlib import Path
import numpy as np
from refractiveindex import RefractiveIndexMaterial

# Предполагаем, что файл с классом RefractiveIndexMaterial находится в текущей директории
# или вы импортируете его оттуда. Для простоты скопируем сюда необходимые импорты.
# (В реальности лучше сделать import refractiveindex, но здесь покажем полный скрипт)

# Скопируйте сюда определение класса RefractiveIndexMaterial и вспомогательные функции
# из предоставленного вами файла (они занимают ~250 строк). 
# Для краткости я не буду копировать их в ответ, а просто буду использовать импорт.
# Предположим, что вы сохранили тот код как "refractiveindex.py" рядом со скриптом.


def collect_uniaxial_n(db_path: Path, wavelength_um=0.63):
    """
    Обходит базу данных, находит файлы с direction='o' и 'e',
    вычисляет показатели преломления на заданной длине волны (в мкм).
    Возвращает словарь { (shelf, book): {'o': n_o, 'e': n_e} }.
    """
    from refractiveindex import RefractiveIndexMaterial
    from refractiveindex import _load_catalog

    # Загружаем каталог
    catalog = _load_catalog(db_path)

    results = {}  # (shelf, book) -> {'o': n, 'e': n}

    for (shelf, book, page), yaml_path in catalog.items():
        # Читаем YAML файл, чтобы узнать direction
        import yaml
        with open(yaml_path, 'rt', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        direction = None
        # Ищем в CONDITIONS
        conditions = data.get('CONDITIONS', {})
        if 'direction' in conditions:
            direction = conditions['direction'].lower()
        # Если нет, пробуем найти в COMMENTS (менее надёжно)
        if not direction:
            comments = data.get('COMMENTS', '')
            if 'ordinary' in comments.lower() or '(o)' in comments:
                direction = 'o'
            elif 'extraordinary' in comments.lower() or '(e)' in comments:
                direction = 'e'
        
        if direction not in ('o', 'e'):
            continue   # не интересует
        
        # Создаём объект материала для этого файла
        try:
            mat = RefractiveIndexMaterial(shelf, book, page, db_path=db_path, auto_download=False)
        except Exception as e:
            print(f"Ошибка загрузки {shelf}/{book}/{page}: {e}", file=sys.stderr)
            continue

        # Проверяем, покрывается ли длина волны
        wl_range = mat.get_wl_range(unit='um')
        if wl_range is None:
            continue
        wl_min, wl_max = wl_range
        if not (wl_min <= wavelength_um <= wl_max):
            continue

        # Вычисляем показатель преломления
        try:
            n = mat.get_refractive_index(wavelength_um, unit='um')
        except Exception as e:
            print(f"Не удалось вычислить n для {shelf}/{book}/{page}: {e}", file=sys.stderr)
            continue

        # Сохраняем
        key = (shelf, book)
        if key not in results:
            results[key] = {}
        results[key][direction] = n

    # Оставляем только те материалы, где есть оба направления
    complete = {k: v for k, v in results.items() if 'o' in v and 'e' in v}
    return complete


if __name__ == '__main__':
    # Укажите путь к вашей локальной копии базы
    db_path = Path(__file__).parent / "database"
    
    data = collect_uniaxial_n(db_path, wavelength_um=0.63)
    print(f"Найдено {len(data)} одноосных кристаллов с n_o и n_e на 630 нм\n")
    for (shelf, book), ns in data.items():
        print(f"{shelf}/{book}: n_o = {ns['o']:.6f}, n_e = {ns['e']:.6f}")