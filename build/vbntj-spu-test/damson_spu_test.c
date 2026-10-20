/* Manual-only Crypto API test. Never installed or autoloaded. */
#include <linux/module.h>
#include <linux/crypto.h>
#include <linux/completion.h>
#include <linux/skbuff.h>
#include <linux/rtnetlink.h>
#include <crypto/aead.h>
#include <crypto/authenc.h>

static DECLARE_COMPLETION(done);
static int request_result;
static bool timed_out;

static void completed(struct crypto_async_request *req, int err)
{
    if (err == -EINPROGRESS)
        return;
    request_result = err;
    complete(&done);
}

static int finish(int err)
{
    if (err != -EINPROGRESS && err != -EBUSY)
        return err;
    if (!wait_for_completion_timeout(&done, 10 * HZ)) {
        /* Preserve the outstanding request, buffers and callback code. */
        timed_out = true;
        __module_get(THIS_MODULE);
        return -ETIMEDOUT;
    }
    return request_result;
}

static int check(const char *hash, unsigned int authsize, bool corrupt)
{
    struct crypto_aead *sw, *hw;
    struct aead_request *enc = NULL, *dec = NULL;
    struct scatterlist assoc, data;
    struct sk_buff *skb = NULL;
    char name[96], driver[96];
    unsigned char key[RTA_SPACE(sizeof(struct crypto_authenc_key_param)) + 48];
    unsigned char iv[16], plain[32];
    unsigned char *buf;
    struct rtattr *rta = (void *)key;
    struct crypto_authenc_key_param *param;
    unsigned int i;
    unsigned int keylen = RTA_SPACE(sizeof(struct crypto_authenc_key_param)) +
                          (!strcmp(hash, "sha1") ? 20 : 32) + 16;
    int err;

    snprintf(name, sizeof(name), "authenc(hmac(%s),cbc(aes))", hash);
    snprintf(driver, sizeof(driver), "authenc(hmac(%s-spu),cbc(aes-spu))", hash);
    sw = crypto_alloc_aead(name, 0, CRYPTO_ALG_ASYNC | CRYPTO_ALG_NEED_FALLBACK);
    if (IS_ERR(sw))
        return PTR_ERR(sw);
    hw = crypto_alloc_aead(driver, 0, 0);
    if (IS_ERR(hw)) {
        err = PTR_ERR(hw);
        goto free_sw;
    }
    memset(key, 0, sizeof(key));
    rta->rta_type = CRYPTO_AUTHENC_KEYA_PARAM;
    rta->rta_len = RTA_LENGTH(sizeof(*param));
    param = RTA_DATA(rta);
    param->enckeylen = cpu_to_be32(16);
    for (i = RTA_SPACE(sizeof(*param)); i < keylen; i++)
        key[i] = (unsigned char)i;
    err = crypto_aead_setkey(sw, key, keylen);
    if (!err)
        err = crypto_aead_setkey(hw, key, keylen);
    if (!err)
        err = crypto_aead_setauthsize(sw, authsize);
    if (!err)
        err = crypto_aead_setauthsize(hw, authsize);
    if (err)
        goto free_hw;
    skb = alloc_skb(256, GFP_KERNEL);
    if (!skb) {
        err = -ENOMEM;
        goto free_hw;
    }
    skb_reserve(skb, 64);
    buf = skb_put(skb, 8 + 16 + sizeof(plain) + authsize);
    memset(buf, 0, skb->len);
    buf[3] = 1; /* ESP SPI and sequence, no network configuration changes. */
    buf[7] = 1;
    for (i = 0; i < sizeof(iv); i++)
        iv[i] = buf[8 + i] = (unsigned char)(i + 1);
    for (i = 0; i < sizeof(plain); i++)
        plain[i] = buf[24 + i] = (unsigned char)(0x20 + i);
    /* Valid ESP trailer: two padding bytes, padlen, next-header. */
    plain[28] = buf[52] = 1;
    plain[29] = buf[53] = 2;
    plain[30] = buf[54] = 2;
    plain[31] = buf[55] = 4;
    sg_init_one(&assoc, buf, 8);
    sg_init_one(&data, buf + 24, sizeof(plain) + authsize);
    enc = aead_request_alloc(sw, GFP_KERNEL);
    dec = aead_request_alloc(hw, GFP_KERNEL);
    if (!enc || !dec) {
        err = -ENOMEM;
        goto free_requests;
    }
    reinit_completion(&done);
    aead_request_set_callback(enc, 0, completed, skb);
    aead_request_set_assoc(enc, &assoc, 8);
    aead_request_set_crypt(enc, &data, &data, sizeof(plain), iv);
    err = finish(crypto_aead_encrypt(enc));
    if (err)
        goto free_requests;
    if (corrupt)
        buf[24 + sizeof(plain)] ^= 0x80;
    reinit_completion(&done);
    aead_request_set_callback(dec, 0, completed, skb);
    aead_request_set_assoc(dec, &assoc, 8);
    aead_request_set_crypt(dec, &data, &data, sizeof(plain) + authsize, buf + 8);
    dec->data_offset = 0;
    err = finish(crypto_aead_decrypt(dec));
    if (corrupt)
        err = err == -EBADMSG ? 0 : (err ? err : -EIO);
    else if (!err && memcmp(buf + 24, plain, sizeof(plain)))
        err = -EIO;
free_requests:
    if (timed_out) {
        pr_err("damson_spu_test: timeout; retaining outstanding request; reboot needed before retry\n");
        return -ETIMEDOUT;
    }
    aead_request_free(enc);
    aead_request_free(dec);
    kfree_skb(skb);
free_hw:
    crypto_free_aead(hw);
free_sw:
    crypto_free_aead(sw);
    pr_info("damson_spu_test: %s-%u %s: %s (%d)\n", hash, authsize * 8,
            corrupt ? "reject-tamper" : "decrypt", err ? "FAIL" : "PASS", err);
    return err;
}

static int __init test_init(void)
{
    int err;
    err = check("sha256", 16, false);
    if (!err)
        err = check("sha256", 16, true);
    if (!err)
        err = check("sha1", 12, false);
    if (!err)
        err = check("sha1", 12, true);
    if (!err)
        pr_info("damson_spu_test: ALL PASS\n");
    /* On timeout remain resident to preserve the outstanding callback. */
    return timed_out ? 0 : err;
}
static void __exit test_exit(void) {}
module_init(test_init);
module_exit(test_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Manual Damson SPU hardware and SHA256-128 fallback test");
