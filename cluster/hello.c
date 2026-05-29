/* hello.c - Task 1: kiem tra OpenMPI chay tren 1 may.
 * Bien dich:  mpicc hello.c -o hello
 * Chay:       mpirun -np 4 ./hello
 */
#include <mpi.h>
#include <stdio.h>

int main(int argc, char **argv) {
    MPI_Init(&argc, &argv);

    int rank, size, len;
    char node[MPI_MAX_PROCESSOR_NAME];
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &size);
    MPI_Get_processor_name(node, &len);

    printf("Hello tu process %d / %d tren may %s\n", rank, size, node);

    MPI_Finalize();
    return 0;
}
