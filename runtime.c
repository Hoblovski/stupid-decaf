#include <stdio.h>
#include <stdarg.h>

void __print(long noeol, long num, ...) {
    va_list ap;
    va_start(ap, num);

    while (num--) {
        long t = va_arg(ap, long);
        printf("%ld ", t);
    }
    if (!noeol)
        printf("\n");
}
