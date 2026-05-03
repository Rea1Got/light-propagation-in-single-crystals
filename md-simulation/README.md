# md-simulation

Молекулярно-динамическая часть проекта по двулучепреломляющим монокристаллам.
Берёт список кристаллов от стадии `crystals-search/`, привязывает их к Materials Project, генерирует LAMMPS-структуры и запускает MD.

## Поток данных

```
crystals-search/crystals_540nm.csv          (39 кандидатов)
        ↓                       mp_init.py  (Materials Project API + whitelist)
crystals_540nm_mp.csv                       (+ mp_id)
        ↓                       (скачивает CIF/VASP)
mp_init/                                    (74 файла структур)
        ↓                       cif_to_lmp.py  (pymatgen → LAMMPS, суперъячейка 2×2×4)
lammps_init/                                (37 *.lmp data-файлов)
        ↓                       gen_inputs.py  (читает potentials.csv + in.template)
inputs/in.<material>                        (8 готовых KIM-скриптов)
        ↓                       run.sh + LAMMPS
dumps/dump.<material>, logs/log.<material>
```

## Структура

```
md-simulation/
├── mp_init.py              # crystals_540nm.csv + MP API → crystals_540nm_mp.csv + mp_init/
├── cif_to_lmp.py           # mp_init/*.cif|*.vasp → lammps_init/*.lmp
├── gen_inputs.py           # potentials.csv + in.template → inputs/in.<material>
├── run.sh                  # Slurm-обёртка; принимает $1 или SLURM_ARRAY_TASK_ID
│
├── potentials/
│   ├── potentials.csv          # реестр потенциалов (см. ниже)
│   ├── kim_verification.md     # отчёт о верификации KIM-моделей (2026-05)
│   ├── GaN.tersoff             # Nord et al. 2003 (не используется, KIM SW предпочтительнее)
│   └── SiC.vashishta           # Vashishta 2007 (скачан из lammps/lammps github)
│
├── inputs/
│   ├── in.template             # параметризованный шаблон LAMMPS-input
│   └── in.<material>           # 8 сгенерированных скриптов: GaN, SiC, BN, Al2O3,
│                               # SiO2, TiO2, ZnO, CdS
│
├── mp_init/                # CIF/VASP, скачано из Materials Project (74 файла)
├── lammps_init/            # LAMMPS data-файлы, ×2×2×4 суперъячейки (37 файлов)
├── dumps/                  # MD-траектории (LAMMPS dump format)
└── logs/                   # LAMMPS-логи + Slurm stdout/stderr
```

## Реестр потенциалов: `potentials/potentials.csv`

Колонки: `material, mp_id, pair_style, potential_ref, file, source, used_in, status, reference, notes`

Значения `status`:
- **`kim`** — модель в OpenKIM, ID верифицирован, файлов на диске не нужно (KIM API подгружает в runtime). Шаблон рендерится через `kim init` + `kim interactions`.
- **`local`** — литературный потенциал, файл параметров **присутствует** в `potentials/`.
- **`local_pending`** — литературный потенциал, файл параметров **отсутствует** (отложен до ручного выписывания из публикации). Пропускается генератором.
- **`needs_dft`** — нет работающего классического потенциала; материал требует DFT-MD (вне текущей инфраструктуры).
- **`none`** — пути нет (для текущих 39 материалов не используется).

При добавлении нового материала: один ряд на (material, candidate_potential). Если есть и KIM, и литературный — два ряда; `kim` имеет приоритет в `gen_inputs.py`.

## Текущее покрытие (39 материалов)

| status | count | материалы |
|---|---|---|
| **kim** | 8 | GaN, SiC, BN, Al2O3, SiO2, TiO2, ZnO, CdS |
| **local** | 2 (на диске) | GaN.tersoff (не используется), SiC.vashishta |
| **local_pending** | 11 | AlN, CaCO3, LaF3, MgF2, YLiF4, AlPO4, KH2PO4, NH4H2PO4 + 4 backup-ряда (Al2O3, SiO2, TiO2, ZnO) |
| **needs_dft** | 23 | все ферроэлектрики (LiNbO3, LiTaO3, BaTiO3, PbTiO3), молибдаты/вольфраматы (CaMoO4, PbMoO4, SrMoO4, CaWO4), бораты (BaB2O4, CsLiB6O10, LuAl3(BO3)4), халькопириты (AgGaS2, CdGa2S4), сложные смеси (CaGdAlO4, CaYAlO4, ScAlMgO4, LiCaAlF6, Pb5Ge3O11), TeO2, BeO, GaS, LiIO3, YVO4 |

Тракт классического MD охватывает **8/39 материалов** (без сбора локальных файлов).

## Использование

### 1. Сгенерировать input-скрипты

```bash
cd md-simulation
python gen_inputs.py
```

Генератор:
- Читает `potentials/potentials.csv` и берёт по одному ряду на материал (`kim > local`).
- Парсит секцию `Masses` из `lammps_init/<material>.lmp` для определения порядка видов.
- Подставляет в `inputs/in.template` блоки `kim init` / `kim interactions` или `pair_style` / `pair_coeff`.
- Записывает `inputs/in.<material>` для каждого материала со status ∈ {kim, local}.
- Пропускает `local_pending` и `needs_dft`.

Зависимостей нет, кроме stdlib.

### 2. Запустить MD

Один материал:
```bash
sbatch run.sh GaN
```

Массив на все 8 KIM-материалов:
```bash
sbatch --array=0-7 run.sh
```

`run.sh` стартует из `md-simulation/`, читает `inputs/in.<material>`, пишет в `dumps/` и `logs/`.

### 3. Workflow при добавлении нового материала

1. Найти потенциал, добавить ряд в `potentials.csv` (или, если потенциала нет — пометить `needs_dft`).
2. Если ряд `kim` — KIM API всё подгрузит сам.
3. Если ряд `local` — положить файл параметров в `potentials/<file>` и сменить status с `local_pending` на `local`.
4. Перегенерировать: `python gen_inputs.py`.
5. Добавить материал в массив `MATERIALS=(...)` в `run.sh`.

## Что **не** входит в эту директорию

- **Оптический пайплайн** — связь MD-траекторий с n_o, n_e на 540 нм. Это центральный исследовательский шаг проекта, методология выбирается научруком.
- **DFT-расчёты** — `status=needs_dft` материалы (~60% списка) не покрываются текущей инфраструктурой.

## Конвенции

- Все пути в `in.<material>` относительны `md-simulation/`, потому что `lmp` запускается оттуда (а не из `inputs/`).
- LAMMPS data-файлы используют `atom_style charge` (формат от pymatgen). Для Tersoff/SW заряды нулевые и игнорируются; для Buckingham/SMTBQ они нужны (см. ниже).
- Для **TiO2** (Matsui-Akaogi Buckingham SM) data-файл от pymatgen имеет нулевые заряды. Если KIM SM не выставит формальные заряды (Ti +2.196, O −1.098) сам, нужно добавить `set type N charge ...` после `kim interactions` в `in.template`. Уточнить при первом запуске.
- Для **Al2O3** (SMTBQ) заряды уравновешиваются динамически — нулевой старт безопасен.
