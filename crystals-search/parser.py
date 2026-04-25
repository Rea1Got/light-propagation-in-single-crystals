"""
pip install refractiveindex

модуль refractiveindex чуть криво работает; я весь код из ".refractiveindex" который вызывается в 
RefractiveIndexMaterial вставил напрямую в __init__.py файл; только таким образом заработало.

В общем, код ищет данные в директориях соединений с суффиксами связанными с "o", "e" и считает по дисперсионной формуле
https://refractiveindex.info/database/doc/Dispersion%20formulas.pdf 
значения коэффициентов двулучепреломления для фиксированной длины волны, после чего сохраняет в файле .csv
"""


import sys
import csv
import re
import warnings
from pathlib import Path
import numpy as np
import yaml
from refractiveindex import RefractiveIndexMaterial, _load_catalog, NoExtinctionCoefficient

def get_suffix_from_page(page_name):
    """Возвращает 'o' или 'e', если имя страницы оканчивается на -o, _o, -e, _e (до .yml)."""
    base = page_name
    if base.endswith('.yml'):
        base = base[:-4]
    if base.endswith('-o') or base.endswith('_o'):
        return 'o'
    if base.endswith('-e') or base.endswith('_e'):
        return 'e'
    return None

def suffixes_are_o_and_e(page1, page2):
    s1 = get_suffix_from_page(page1)
    s2 = get_suffix_from_page(page2)
    return s1 == 'o' and s2 == 'e' or s1 == 'e' and s2 == 'o'

def has_suffix_o_e(page_name):
    """Проверяет, заканчивается ли имя страницы на -o, -e, _o, _e, или содержит -o/, -e/."""
    return bool(re.search(r'[-_](o|e)(\b|$)', page_name, re.IGNORECASE))

def safe_n_and_k(mat, wavelength_um):
    with warnings.catch_warnings():
        warnings.filterwarnings('error', category=RuntimeWarning)
        try:
            n = mat.get_refractive_index(wavelength_um, unit='um')
            if np.isnan(n) or np.isinf(n) or n < 1.2:
                return None, None
            try:
                k = mat.get_extinction_coefficient(wavelength_um, unit='um')
                if np.isnan(k) or np.isinf(k):
                    k = 0.0
            except NoExtinctionCoefficient:
                k = 0.0
            return n, k
        except:
            return None, None

def collect_uniaxial_pairs(db_path, wavelength_um=0.63, min_diff=0.01, max_k=0.01):
    catalog = _load_catalog(db_path)
    # Собираем все записи (shelf, book, suffix, n, page, k)
    records = []  # (shelf, book, suffix, n, page, k)
    
    for (shelf, book, page), yaml_path in catalog.items():
        if shelf != ('main' or 'organic'):
            continue
        
        # Определяем суффикс o/e по имени страницы
        suffix = get_suffix_from_page(page)
        if suffix is None:
            continue
        
        try:
            mat = RefractiveIndexMaterial(shelf, book, page, db_path=db_path, auto_download=False)
        except Exception:
            continue
        
        wl_range = mat.get_wl_range(unit='um')
        if wl_range is None:
            continue
        wl_min, wl_max = wl_range
        if not (wl_min <= wavelength_um <= wl_max):
            continue
        
        n, k = safe_n_and_k(mat, wavelength_um)
        if n is None or k > max_k:
            continue
        if book == 'ZnO':
            print(f"DEBUG: {page} | suffix={suffix} | wl_range={wl_range} | n={n} | k={k}")
        records.append((shelf, book, suffix, n, page, k))
    
    # Группируем по (shelf, book)
    from collections import defaultdict
    books = defaultdict(lambda: {'o': [], 'e': []})
    for (shelf, book, suffix, n, page, k) in records:
        books[(shelf, book)][suffix].append((n, page, k))
    
    # Для каждой книги выбираем лучший o и лучший e
    candidates = {}
    for (shelf, book), dirs in books.items():
        o_list = dirs['o']
        e_list = dirs['e']
        if not o_list or not e_list:
            continue
        # Выбираем запись с минимальным k (если k равны, то первую)
        best_o = min(o_list, key=lambda x: x[2])  # (n, page, k)
        best_e = min(e_list, key=lambda x: x[2])
        n_o, page_o, k_o = best_o
        n_e, page_e, k_e = best_e
        if abs(n_o - n_e) >= min_diff:
            candidates[(shelf, book)] = (n_o, n_e, page_o, page_e)
    
    return candidates

if __name__ == '__main__':
    db_path = Path(__file__).parent / "database"
    wavelength_um = 0.54   # можно менять при необходимости
    pairs = collect_uniaxial_pairs(db_path, wavelength_um=wavelength_um, 
                                   min_diff=0.001, max_k=0.01)
    
    print(f"Отфильтровано (только o/e суффиксы, без поглощения): {len(pairs)}")
    for (shelf, book), (n1, n2, p1, p2) in pairs.items():
        print(f"{shelf}/{book}: {n1:.6f} ({p1}), {n2:.6f} ({p2})")
    
    # Сохранение в CSV
    output_filename = f"crystals_{wavelength_um*1000:.0f}nm.csv"
    with open(output_filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['shelf', 'book', 'n_o', 'n_e', 'page_o', 'page_e', 'wavelength_um'])
        for (shelf, book), (n_o, n_e, page_o, page_e) in pairs.items():
            writer.writerow([shelf, book, n_o, n_e, page_o, page_e, wavelength_um])
    
    print(f"\nРезультаты сохранены в {output_filename}")