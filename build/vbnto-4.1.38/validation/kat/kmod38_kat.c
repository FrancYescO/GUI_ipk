/* Temporary known-answer tests. Never installed or loaded at boot. */
#include <linux/module.h>
#include <linux/slab.h>
#include <linux/scatterlist.h>
#include <linux/nls.h>
#include <crypto/hash.h>
#include <linux/crypto.h>

static char *test = "sha256";
module_param(test, charp, 0444);

static bool matches_hex(const u8 *bytes, unsigned int length, const char *hex)
{
    static const char digits[] = "0123456789abcdef";
    unsigned int i;
    for (i = 0; i < length; i++)
        if (digits[bytes[i] >> 4] != hex[i * 2] ||
            digits[bytes[i] & 15] != hex[i * 2 + 1])
            return false;
    return true;
}

static int hash_test(const char *driver, const char *input, const char *expected)
{
    struct crypto_shash *tfm;
    struct shash_desc *desc;
    u8 output[64];
    int error;
    tfm = crypto_alloc_shash(driver, 0, 0);
    if (IS_ERR(tfm))
        return PTR_ERR(tfm);
    desc = kzalloc(sizeof(*desc) + crypto_shash_descsize(tfm), GFP_KERNEL);
    if (!desc) {
        crypto_free_shash(tfm);
        return -ENOMEM;
    }
    desc->tfm = tfm;
    error = crypto_shash_digest(desc, input, strlen(input), output);
    if (!error && !matches_hex(output, crypto_shash_digestsize(tfm), expected))
        error = -EBADMSG;
    kfree(desc);
    crypto_free_shash(tfm);
    return error;
}

static int cipher_test(bool counter)
{
    struct crypto_blkcipher *tfm;
    struct blkcipher_desc desc;
    struct scatterlist sg;
    u8 key[16] = { 0 }, iv[16] = { 0 };
    u8 *data;
    unsigned int i;
    int error;
    const char *expected = counter ?
        "66e94bd4ef8a2c3b884cfa59ca342b2e58e2fccefa7e3061367f1d57a4e7455a" :
        "66e94bd4ef8a2c3b884cfa59ca342b2e66e94bd4ef8a2c3b884cfa59ca342b2e";
    tfm = crypto_alloc_blkcipher(counter ? "ctr(aes-generic)" : "ecb(aes-generic)",
                                0, CRYPTO_ALG_ASYNC);
    if (IS_ERR(tfm))
        return PTR_ERR(tfm);
    data = kzalloc(32, GFP_KERNEL);
    if (!data) {
        crypto_free_blkcipher(tfm);
        return -ENOMEM;
    }
    desc.tfm = tfm;
    desc.flags = 0;
    desc.info = iv;
    error = crypto_blkcipher_setkey(tfm, key, sizeof(key));
    sg_init_one(&sg, data, 32);
    if (!error)
        error = crypto_blkcipher_encrypt_iv(&desc, &sg, &sg, 32);
    if (!error && !matches_hex(data, 32, expected))
        error = -EBADMSG;
    memset(iv, 0, sizeof(iv));
    if (!error)
        error = crypto_blkcipher_decrypt_iv(&desc, &sg, &sg, 32);
    for (i = 0; !error && i < 32; i++)
        if (data[i])
            error = -EBADMSG;
    kfree(data);
    crypto_free_blkcipher(tfm);
    return error;
}

static int compression_test(void)
{
    static const u8 encoded[] = { 0xcb, 0x48, 0xcd, 0xc9, 0xc9, 0x57, 0x28,
                                  0xcf, 0x2f, 0xca, 0x49, 0x01, 0x00 };
    struct crypto_comp *tfm = crypto_alloc_comp("deflate", 0, 0);
    u8 clear[128], compressed[128];
    unsigned int size = sizeof(clear), compressed_size = sizeof(compressed);
    int error;
    if (IS_ERR(tfm))
        return PTR_ERR(tfm);
    error = crypto_comp_decompress(tfm, encoded, sizeof(encoded), clear, &size);
    if (!error && (size != 11 || memcmp(clear, "hello world", 11)))
        error = -EBADMSG;
    if (!error)
        error = crypto_comp_compress(tfm, clear, size, compressed, &compressed_size);
    size = sizeof(clear);
    if (!error)
        error = crypto_comp_decompress(tfm, compressed, compressed_size, clear, &size);
    if (!error && (size != 11 || memcmp(clear, "hello world", 11)))
        error = -EBADMSG;
    crypto_free_comp(tfm);
    return error;
}

static int nls_test(void)
{
    struct nls_table *nls = load_nls("utf8");
    static const u8 euro[] = { 0xe2, 0x82, 0xac };
    u8 encoded[8];
    wchar_t character;
    int error = 0;
    if (!nls)
        return -ENOENT;
    if (nls->char2uni(euro, sizeof(euro), &character) != 3 || character != 0x20ac ||
        nls->uni2char(character, encoded, sizeof(encoded)) != 3 ||
        memcmp(encoded, euro, sizeof(euro)))
        error = -EBADMSG;
    unload_nls(nls);
    return error;
}

static int __init run_tests(void)
{
    int error;
    if (!strcmp(test, "sha256"))
        error = hash_test("sha256-generic", "abc",
                         "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
    else if (!strcmp(test, "sha512"))
        error = hash_test("sha512-generic", "abc",
            "ddaf35a193617abacc417349ae20413112e6fa4e89a97ea20a9eeee64b55d39a"
            "2192992a274fc1a836ba3c23a3feebbd454d4423643ce80e2a9ac94fa54ca49f");
    else if (!strcmp(test, "crc32c"))
        error = hash_test("crc32c-generic", "123456789", "839206e3");
    else if (!strcmp(test, "ecb"))
        error = cipher_test(false);
    else if (!strcmp(test, "ctr"))
        error = cipher_test(true);
    else if (!strcmp(test, "deflate"))
        error = compression_test();
    else if (!strcmp(test, "nls"))
        error = nls_test();
    else
        error = -EINVAL;
    pr_info("kmod38_kat: %s %s (%d)\n", test, error ? "FAIL" : "PASS", error);
    return error;
}

static void __exit done(void) {}
module_init(run_tests);
module_exit(done);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Temporary stock-ABI candidate known-answer tests");
