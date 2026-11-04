/* Test-process-only redirection. No global node or library changes. */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <fcntl.h>
#include <stdarg.h>
#include <string.h>
#include <errno.h>
#include <unistd.h>

#ifndef SPU_CRYPTO_FROM
#define SPU_CRYPTO_FROM "/dev/crypto"
#endif
#ifndef SPU_CRYPTO_TO
#define SPU_CRYPTO_TO "/dev/crypto-cbc-lab"
#endif

int spu_crypto_redirect_active(void) { return 1; }

static int forward(const char *symbol, const char *path, int flags, mode_t mode)
{
    int (*real_open)(const char *, int, ...) = dlsym(RTLD_NEXT, symbol);
    if (!real_open) real_open = dlsym(RTLD_NEXT, "open");
    if (!real_open) { errno = ENOSYS; return -1; }
    if (!strcmp(path, SPU_CRYPTO_FROM)) {
        static const char message[] = "cryptodev-lab: redirected device open\n";
        path = SPU_CRYPTO_TO;
        write(STDERR_FILENO, message, sizeof(message) - 1);
    }
    return real_open(path, flags, mode);
}
int open(const char *path, int flags, ...)
{
    va_list args;
    mode_t mode = 0;
    if (flags & O_CREAT) { va_start(args, flags); mode = va_arg(args, mode_t); va_end(args); }
    return forward("open", path, flags, mode);
}
int open64(const char *path, int flags, ...)
{
    va_list args;
    mode_t mode = 0;
    if (flags & O_CREAT) { va_start(args, flags); mode = va_arg(args, mode_t); va_end(args); }
    return forward("open64", path, flags, mode);
}
int __open_2(const char *path, int flags) { return forward("open", path, flags, 0); }
int __open64_2(const char *path, int flags) { return forward("open64", path, flags, 0); }
