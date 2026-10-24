#include <stdio.h>
#include <omp.h>
int main(void) {
    int sum = 0, threads = 0;
    omp_set_dynamic(0);
    #pragma omp parallel num_threads(4) reduction(+:sum)
    {
        #pragma omp single
        threads = omp_get_num_threads();
        #pragma omp for
        for (int i = 1; i <= 100; ++i) sum += i;
    }
    printf("threads=%d sum=%d\n", threads, sum);
    return threads == 4 && sum == 5050 ? 0 : 1;
}
