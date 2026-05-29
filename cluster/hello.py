#!/usr/bin/env python3
"""hello.py - Task 1: kiem tra mpi4py chay tren 1 may.
Chay: mpirun -np 4 python3 hello.py
"""
from mpi4py import MPI

comm = MPI.COMM_WORLD
rank = comm.Get_rank()
size = comm.Get_size()
node = MPI.Get_processor_name()

print(f"Hello tu process {rank} / {size} tren may {node}")
