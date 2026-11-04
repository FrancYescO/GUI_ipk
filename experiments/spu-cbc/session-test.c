/* Valid requests only, and only against the isolated patched lab bridge. */
#include <crypto/cryptodev.h>
#include <sys/ioctl.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <sys/resource.h>

static int fd;
static void check(int ok, const char *message)
{
    if (!ok) { perror(message); exit(1); }
    printf("PASS %s\n", message);
}
static void info(unsigned int session)
{
    struct session_info_op s = {0};
    s.ses = session;
    check(!ioctl(fd, CIOCGSESSINFO, &s), "session info");
    printf("driver cipher=%s\n", s.cipher_info.cra_driver_name);
}
static void valid_cbc(void)
{
    unsigned char key[] = {0x2b,0x7e,0x15,0x16,0x28,0xae,0xd2,0xa6,0xab,0xf7,0x15,0x88,0x09,0xcf,0x4f,0x3c};
    unsigned char plain[16] = {0x6b,0xc1,0xbe,0xe2,0x2e,0x40,0x9f,0x96,0xe9,0x3d,0x7e,0x11,0x73,0x93,0x17,0x2a};
    unsigned char expected[] = {0x76,0x49,0xab,0xac,0x81,0x19,0xb2,0x46,0xce,0xe9,0x8e,0x9b,0x12,0xe9,0x19,0x7d};
    unsigned char iv[16], input[16], output[16];
    struct session_op s = {0};
    struct crypt_op c = {0};
    int i, inplace;
    s.cipher = CRYPTO_AES_CBC; s.keylen = sizeof(key); s.key = key;
    check(!ioctl(fd, CIOCGSESSION, &s), "NIST session");
    info(s.ses);
    c.ses = s.ses; c.len = 16; c.iv = iv;
    for (inplace = 0; inplace < 2; inplace++) {
        memcpy(input, plain, 16);
        for (i = 0; i < 16; i++) iv[i] = i;
        c.op = COP_ENCRYPT; c.src = input; c.dst = inplace ? input : output;
        check(!ioctl(fd, CIOCCRYPT, &c) && !memcmp(c.dst, expected, 16), "NIST encrypt");
        for (i = 0; i < 16; i++) iv[i] = i;
        c.op = COP_DECRYPT; c.src = c.dst; c.dst = input;
        check(!ioctl(fd, CIOCCRYPT, &c) && !memcmp(input, plain, 16), "NIST decrypt");
    }
    check(!ioctl(fd, CIOCFSESSION, &s.ses), "close NIST session");
}

static unsigned long long ns(const struct timespec *t)
{
    return (unsigned long long)t->tv_sec * 1000000000ULL + t->tv_nsec;
}
static unsigned long long cpu_us(const struct rusage *r)
{
    return (unsigned long long)(r->ru_utime.tv_sec + r->ru_stime.tv_sec) * 1000000ULL +
           r->ru_utime.tv_usec + r->ru_stime.tv_usec;
}
static void benchmark(void)
{
    unsigned char key[16] = {0}, iv[16], plain[1408], cipher[1408], output[1408];
    struct session_op s = {0};
    struct crypt_op c = {0};
    struct timespec begin, end;
    struct rusage before, after;
    unsigned long long elapsed, kib;
    unsigned int i, n, direction;
    for (i = 0; i < sizeof(plain); i++) plain[i] = i * 31;
    s.cipher = CRYPTO_AES_CBC; s.keylen = 16; s.key = key;
    check(ioctl(fd, CIOCGSESSION, &s) == 0, "benchmark session");
    info(s.ses);
    c.ses = s.ses; c.len = sizeof(plain); c.iv = iv;
    for (direction = 0; direction < 2; direction++) {
        c.op = direction ? COP_DECRYPT : COP_ENCRYPT;
        c.src = direction ? cipher : plain;
        c.dst = direction ? output : cipher;
        getrusage(RUSAGE_SELF, &before);
        clock_gettime(CLOCK_MONOTONIC, &begin);
        for (n = 0; n < 128; n++) {
            for (i = 0; i < 16; i++) iv[i] = i;
            if (ioctl(fd, CIOCCRYPT, &c)) { perror("benchmark crypt"); exit(1); }
        }
        clock_gettime(CLOCK_MONOTONIC, &end);
        getrusage(RUSAGE_SELF, &after);
        elapsed = ns(&end) - ns(&begin);
        kib = sizeof(plain) * 128ULL * 1000000000ULL / elapsed / 1024;
        printf("BENCH %s bytes=%u elapsed_ns=%llu process_cpu_us=%llu KiB/s=%llu\n",
               direction ? "decrypt" : "encrypt", (unsigned int)sizeof(plain) * 128,
               elapsed, cpu_us(&after) - cpu_us(&before), kib);
    }
    check(!memcmp(plain, output, sizeof(plain)), "benchmark roundtrip");
    check(ioctl(fd, CIOCFSESSION, &s.ses) == 0, "close benchmark");
}
int main(int argc, char **argv)
{
    setvbuf(stdout, NULL, _IONBF, 0);
    if (argc < 2 || strcmp(argv[1], "/dev/crypto-cbc-lab")) {
        fprintf(stderr, "Only /dev/crypto-cbc-lab is accepted\n");
        return 2;
    }
    fd = open(argv[1], O_RDWR);
    if (fd < 0) { perror("open crypto"); return 1; }
    valid_cbc();
    if (argc > 2 && !strcmp(argv[2], "--bench")) benchmark();
    close(fd);
    return 0;
}
