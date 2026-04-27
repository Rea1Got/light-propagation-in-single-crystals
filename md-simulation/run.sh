#!/bin/bash

#SBATCH -J LAMMPS
#SBATCH -N 1
#SBATCH -t 800
#SBATCH -p small

#SBATCH -o lammps_%j.out
#SBATCH -e lammps_%j.err

# Если потребуется GPU (пока закомментировано):
###SBATCH --gres=gpu:1
###SBATCH --reservation=test

# Если нужно больше потоков на CPU (по умолчанию 1 на Slurm-задачу)
export OMP_NUM_THREADS=16
###export OMP_PROC_BIND=spread

# --- Загрузка окружения ---
# Путь к conda (убедитесь, что он верный; ниже стандартный для вашего пользователя)
source ~/miniconda3/etc/profile.d/conda.sh
conda activate lammps-kim

# Переход в рабочую директорию (поменяйте на фактический путь)
###cd ~/MIPT/md-simulation/mp_init   # или где лежат GaN.lmp и in.GaN

# Запуск LAMMPS
echo "Старт расчёта: $(date)"
lmp -in in.GaN -log log.GaN_run
echo "Завершено: $(date)"
