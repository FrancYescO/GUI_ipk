/* EVP/ENGINE test without depending on the firmware's optional openssl CLI. */
#define _GNU_SOURCE
#include <openssl/evp.h>
#include <openssl/engine.h>
#include <openssl/err.h>
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#define BYTES (256 * 1024)
#define FUNCTIONS(F) \
    F(ERR_print_errors_fp) F(EVP_CIPHER_CTX_new) F(EVP_CIPHER_CTX_free) \
    F(EVP_CipherInit_ex) F(EVP_CIPHER_CTX_set_padding) F(EVP_CipherUpdate) F(EVP_CipherFinal_ex) \
    F(EVP_aes_128_cbc) F(EVP_aes_192_cbc) F(EVP_aes_256_cbc) F(EVP_CIPHER_key_length) \
    F(SSLeay_version) F(ENGINE_load_builtin_engines) F(ENGINE_by_id) F(ENGINE_init) \
    F(ENGINE_finish) F(ENGINE_free)
#define DECLARE(name) static __typeof__(&name) p_##name;
FUNCTIONS(DECLARE)
#undef DECLARE
#define ERR_print_errors_fp p_ERR_print_errors_fp
#define EVP_CIPHER_CTX_new p_EVP_CIPHER_CTX_new
#define EVP_CIPHER_CTX_free p_EVP_CIPHER_CTX_free
#define EVP_CipherInit_ex p_EVP_CipherInit_ex
#define EVP_CIPHER_CTX_set_padding p_EVP_CIPHER_CTX_set_padding
#define EVP_CipherUpdate p_EVP_CipherUpdate
#define EVP_CipherFinal_ex p_EVP_CipherFinal_ex
#define EVP_aes_128_cbc p_EVP_aes_128_cbc
#define EVP_aes_192_cbc p_EVP_aes_192_cbc
#define EVP_aes_256_cbc p_EVP_aes_256_cbc
#define EVP_CIPHER_key_length p_EVP_CIPHER_key_length
#define SSLeay_version p_SSLeay_version
#define ENGINE_load_builtin_engines p_ENGINE_load_builtin_engines
#define ENGINE_by_id p_ENGINE_by_id
#define ENGINE_init p_ENGINE_init
#define ENGINE_finish p_ENGINE_finish
#define ENGINE_free p_ENGINE_free

static void load_symbols(void)
{
    void *library = dlopen("libcrypto.so.1.0.0", RTLD_NOW | RTLD_GLOBAL);
    if (!library) { fprintf(stderr, "%s\n", dlerror()); exit(1); }
#define LOAD(name) do { \
    p_##name = (__typeof__(p_##name))dlsym(library, #name); \
    if (!p_##name) { fprintf(stderr, "Missing symbol %s\n", #name); exit(1); } \
    } while (0);
    FUNCTIONS(LOAD)
#undef LOAD
}
static unsigned long long ns(const struct timespec *t)
{
    return (unsigned long long)t->tv_sec * 1000000000ULL + t->tv_nsec;
}
static void fail(const char *where)
{
    fprintf(stderr, "EVP FAIL %s\n", where);
    ERR_print_errors_fp(stderr);
    exit(1);
}
static void run(const EVP_CIPHER *cipher, ENGINE *engine, int encrypt,
                const unsigned char *input, unsigned char *output,
                const unsigned char *key, const unsigned char *iv)
{
    EVP_CIPHER_CTX *ctx = EVP_CIPHER_CTX_new();
    struct timespec begin, end;
    int a = 0, b = 0;
    unsigned long long elapsed;
    if (!ctx) fail("context allocation");
    clock_gettime(CLOCK_MONOTONIC, &begin);
    if (!EVP_CipherInit_ex(ctx, cipher, engine, key, iv, encrypt)) fail("init");
    if (!engine && ctx->engine) fail("reference unexpectedly selected an engine");
    if (engine && !ctx->engine) fail("requested engine missing");
    EVP_CIPHER_CTX_set_padding(ctx, 0);
    if (!EVP_CipherUpdate(ctx, output, &a, input, BYTES)) fail("update");
    if (!EVP_CipherFinal_ex(ctx, output + a, &b) || a + b != BYTES) fail("final");
    clock_gettime(CLOCK_MONOTONIC, &end);
    elapsed = ns(&end) - ns(&begin);
    printf("EVP %s %s keybits=%d bytes=%d elapsed_ns=%llu KiB/s=%llu\n",
           engine ? "cryptodev" : "software", encrypt ? "encrypt" : "decrypt",
           EVP_CIPHER_key_length(cipher) * 8, BYTES, elapsed,
           BYTES * 1000000000ULL / elapsed / 1024);
    EVP_CIPHER_CTX_free(ctx);
}
int main(void)
{
    const EVP_CIPHER *ciphers[3];
    unsigned char *plain, *expected[3], *actual, *decoded;
    unsigned char key[32], iv[16];
    ENGINE *engine;
    int (*redirect_active)(void) = dlsym(RTLD_DEFAULT, "spu_crypto_redirect_active");
    unsigned int i, c;
    setvbuf(stdout, NULL, _IONBF, 0);
    if (!redirect_active || !redirect_active()) {
        fprintf(stderr, "The private-device redirect must be loaded\n");
        return 2;
    }
    load_symbols();
    printf("LIBRARY %s\n", SSLeay_version(SSLEAY_VERSION));
    ciphers[0] = EVP_aes_128_cbc(); ciphers[1] = EVP_aes_192_cbc(); ciphers[2] = EVP_aes_256_cbc();
    plain = malloc(BYTES); actual = malloc(BYTES + 32); decoded = malloc(BYTES + 32);
    if (!plain || !actual || !decoded) fail("allocation");
    for (i = 0; i < BYTES; i++) plain[i] = i * 31;
    for (i = 0; i < sizeof(key); i++) key[i] = i;
    for (i = 0; i < sizeof(iv); i++) iv[i] = i + 16;
    for (c = 0; c < 3; c++) {
        expected[c] = malloc(BYTES + 32);
        if (!expected[c]) fail("reference allocation");
        run(ciphers[c], NULL, 1, plain, expected[c], key, iv);
        run(ciphers[c], NULL, 0, expected[c], decoded, key, iv);
        if (memcmp(plain, decoded, BYTES)) fail("software roundtrip");
    }
    ENGINE_load_builtin_engines();
    engine = ENGINE_by_id("cryptodev");
    if (!engine || !ENGINE_init(engine)) fail("cryptodev engine");
    for (c = 0; c < 3; c++) {
        run(ciphers[c], engine, 1, plain, actual, key, iv);
        if (memcmp(expected[c], actual, BYTES)) fail("engine ciphertext");
        run(ciphers[c], engine, 0, actual, decoded, key, iv);
        if (memcmp(plain, decoded, BYTES)) fail("engine roundtrip");
        printf("EVP_MATCH_AES%u\n", (unsigned int)EVP_CIPHER_key_length(ciphers[c]) * 8);
        free(expected[c]);
    }
    ENGINE_finish(engine); ENGINE_free(engine);
    free(plain); free(actual); free(decoded);
    return 0;
}
