/* GPL-2.0. Known-answer tests of the explicitly selected private ARM SHA1. */
#include <linux/module.h>
#include <crypto/hash.h>
#include <crypto/sha.h>

static int digest(struct crypto_shash *tfm, const u8 *data, unsigned int len, u8 *out)
{
    SHASH_DESC_ON_STACK(desc, tfm);
    desc->tfm = tfm;
    desc->flags = 0;
    return crypto_shash_digest(desc, data, len, out);
}
static int __init kat_init(void)
{
    static const u8 abc[20] = {0xa9,0x99,0x3e,0x36,0x47,0x06,0x81,0x6a,0xba,0x3e,0x25,0x71,0x78,0x50,0xc2,0x6c,0x9c,0xd0,0xd8,0x9d};
    static const u8 mac[20] = {0xb6,0x17,0x31,0x86,0x55,0x05,0x72,0x64,0xe2,0x8b,0xc0,0xb6,0xfb,0x37,0x8c,0x8e,0xf1,0x46,0xbe,0x00};
    struct crypto_shash *sha, *hmac;
    u8 result[20], key[20];
    int err;
    sha = crypto_alloc_shash("sha1-spu-cbc-lab-arm", 0, 0);
    if (IS_ERR(sha)) return PTR_ERR(sha);
    hmac = crypto_alloc_shash("hmac(sha1-spu-cbc-lab-arm)", 0, 0);
    if (IS_ERR(hmac)) { err = PTR_ERR(hmac); goto free_sha; }
    err = digest(sha, (const u8 *)"abc", 3, result);
    if (!err && memcmp(result, abc, 20)) err = -EBADMSG;
    memset(key, 0x0b, sizeof(key));
    if (!err) err = crypto_shash_setkey(hmac, key, sizeof(key));
    if (!err) err = digest(hmac, (const u8 *)"Hi There", 8, result);
    if (!err && memcmp(result, mac, 20)) err = -EBADMSG;
    memzero_explicit(key, sizeof(key));
    memzero_explicit(result, sizeof(result));
    crypto_free_shash(hmac);
free_sha:
    crypto_free_shash(sha);
    pr_info("spu_sha1_kat: SHA1 abc and HMAC-SHA1 RFC2202: %s (%d)\n", err ? "FAIL" : "PASS", err);
    return err;
}
static void __exit kat_exit(void) { }
module_init(kat_init);
module_exit(kat_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Private ARM SHA1 and HMAC-SHA1 known-answer tests");
