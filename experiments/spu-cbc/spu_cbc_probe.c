/* GPL-2.0. Manual single-request IV/mode capability probe, never autoloaded. */
#include <linux/module.h>
#include <linux/crypto.h>
#include <linux/completion.h>
#include <linux/skbuff.h>
#include <linux/rtnetlink.h>
#include <crypto/aead.h>
#include <crypto/authenc.h>
#include <crypto/algapi.h>
#include <crypto/aes.h>
#include <crypto/hash.h>
#include <crypto/sha.h>

static DECLARE_COMPLETION(done);
static int result;
static bool pending;
static bool downstream_encrypt;
module_param(downstream_encrypt, bool, 0444);
extern int spu_cbc_lab_prepare_encrypt(struct crypto_aead *tfm);

static int authenticate(u8 *frame, const u8 *key)
{
    struct crypto_shash *hash = crypto_alloc_shash("hmac(sha1-generic)", 0, 0);
    u8 digest[SHA1_DIGEST_SIZE];
    int err;
    if (IS_ERR(hash))
        return PTR_ERR(hash);
    err = crypto_shash_setkey(hash, key, 20);
    if (!err) {
        SHASH_DESC_ON_STACK(desc, hash);
        desc->tfm = hash;
        desc->flags = 0;
        err = crypto_shash_digest(desc, frame, 24 + 32, digest);
        if (!err)
            memcpy(frame + 24 + 32, digest, 12);
    }
    memzero_explicit(digest, sizeof(digest));
    crypto_free_shash(hash);
    return err;
}

static void completed(struct crypto_async_request *req, int err)
{
    if (err == -EINPROGRESS)
        return;
    result = err;
    complete(&done);
}

static int compare(const char *name, u8 *key, const u8 *iv,
                   const u8 *plain, const u8 *cipher)
{
    struct crypto_blkcipher *tfm;
    struct blkcipher_desc desc;
    struct scatterlist src, dst;
    u8 actual[32], local_iv[16];
    int err;
    if (!strcmp(name, "ecb(aes)")) {
        struct crypto_cipher *aes = crypto_alloc_cipher("aes-generic", 0, 0);
        if (IS_ERR(aes))
            return PTR_ERR(aes);
        err = crypto_cipher_setkey(aes, key, 16);
        if (!err) {
            crypto_cipher_encrypt_one(aes, actual, plain);
            crypto_cipher_encrypt_one(aes, actual + 16, plain + 16);
            if (memcmp(actual, cipher, 32))
                err = -EBADMSG;
        }
        crypto_free_cipher(aes);
        return err;
    }
    tfm = crypto_alloc_blkcipher(name, 0, CRYPTO_ALG_ASYNC | CRYPTO_ALG_NEED_FALLBACK);
    if (IS_ERR(tfm))
        return PTR_ERR(tfm);
    err = crypto_blkcipher_setkey(tfm, key, 16);
    if (!err) {
        memset(&desc, 0, sizeof(desc));
        memcpy(local_iv, iv, 16);
        desc.tfm = tfm;
        desc.info = local_iv;
        sg_init_one(&src, plain, 32);
        sg_init_one(&dst, actual, 32);
        err = crypto_blkcipher_encrypt_iv(&desc, &dst, &src, 32);
        if (!err && memcmp(actual, cipher, 32))
            err = -EBADMSG;
    }
    crypto_free_blkcipher(tfm);
    return err;
}

static int __init probe_init(void)
{
    struct crypto_aead *hw;
    struct aead_givcrypt_request *req;
    struct scatterlist assoc, payload;
    struct sk_buff *skb;
    struct rtattr *rta;
    struct crypto_authenc_key_param *param;
    u8 key[RTA_SPACE(sizeof(*param)) + 20 + 16];
    u8 plain[32], requested_iv[16];
    u8 *buf, *aeskey;
    int i, err;

    hw = crypto_alloc_aead("lab-authenc(hmac(sha1-spu),cbc(aes-spu))", 0, 0);
    if (IS_ERR(hw)) {
        hw = crypto_alloc_aead("lab-authenc-hmac-sha1-cbc-aes-spu", 0, 0);
        if (IS_ERR(hw))
            return PTR_ERR(hw);
    }
    if (downstream_encrypt) {
        err = spu_cbc_lab_prepare_encrypt(hw);
        if (err)
            goto free_tfm;
    }
    memset(key, 0, sizeof(key));
    rta = (void *)key;
    rta->rta_type = CRYPTO_AUTHENC_KEYA_PARAM;
    rta->rta_len = RTA_LENGTH(sizeof(*param));
    param = RTA_DATA(rta);
    param->enckeylen = cpu_to_be32(16);
    for (i = RTA_SPACE(sizeof(*param)); i < sizeof(key); i++)
        key[i] = i;
    aeskey = key + sizeof(key) - 16;
    err = crypto_aead_setkey(hw, key, sizeof(key));
    if (!err)
        err = crypto_aead_setauthsize(hw, 12);
    if (err)
        goto free_tfm;
    skb = alloc_skb(256, GFP_KERNEL);
    if (!skb) {
        err = -ENOMEM;
        goto free_tfm;
    }
    skb_reserve(skb, 64);
    buf = skb_put(skb, 8 + 16 + 32 + 12);
    memset(buf, 0, skb->len);
    buf[3] = buf[7] = 1;
    for (i = 0; i < 16; i++)
        requested_iv[i] = buf[8 + i] = i + 1;
    for (i = 0; i < 32; i++)
        plain[i] = buf[24 + i] = 0x20 + i;
    /* Keep a valid ESP trailer; no network interfaces or SAs are created. */
    plain[28] = buf[52] = 1;
    plain[29] = buf[53] = 2;
    plain[30] = buf[54] = 2;
    plain[31] = buf[55] = 4;
    req = kzalloc(sizeof(*req) + crypto_aead_reqsize(hw), GFP_KERNEL);
    if (!req) {
        err = -ENOMEM;
        goto free_skb;
    }
    sg_init_one(&assoc, buf, 8);
    sg_init_one(&payload, buf + 24, 32 + 12);
    aead_givcrypt_set_tfm(req, hw);
    aead_givcrypt_set_callback(req, 0, completed, skb);
    aead_givcrypt_set_assoc(req, &assoc, 8);
    aead_givcrypt_set_crypt(req, &payload, &payload, downstream_encrypt ? 44 : 32, buf + 8);
    aead_givcrypt_set_giv(req, buf + 8, 1);
    req->areq.next_hdr = 4;
    req->areq.data_offset = 0;
    if (downstream_encrypt) {
        err = authenticate(buf, key + RTA_SPACE(sizeof(*param)));
        if (!err)
            err = crypto_aead_decrypt(&req->areq);
    } else {
        err = crypto_aead_givencrypt(req);
    }
    /* The vendor returns -EBUSY without enqueueing. */
    if (err == -EINPROGRESS) {
        if (!wait_for_completion_timeout(&done, 10 * HZ)) {
            pending = true;
            __module_get(THIS_MODULE);
            pr_err("spu_cbc_probe: pending request retained; do not stop/unload SPU\n");
            return 0;
        }
        err = result;
    }
    pr_info("spu_cbc_probe: completion=%d\n", err);
    {
        pr_info("spu_cbc_probe: requested_iv_preserved=%d\n",
                !memcmp(buf + 8, requested_iv, 16));
        pr_info("spu_cbc_probe: CBC_requested=%d CBC_returned=%d ECB=%d\n",
                compare("cbc(aes)", aeskey, requested_iv, plain, buf + 24),
                compare("cbc(aes)", aeskey, buf + 8, plain, buf + 24),
                compare("ecb(aes)", aeskey, requested_iv, plain, buf + 24));
    }
    kfree(req);
free_skb:
    kfree_skb(skb);
free_tfm:
    crypto_free_aead(hw);
    /* Successful load also keeps a failed capability result visible in dmesg. */
    return err;
}
static void __exit probe_exit(void) { }
module_init(probe_init);
module_exit(probe_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Private SPU Runner IV/mode capability probe, not a cipher provider");
