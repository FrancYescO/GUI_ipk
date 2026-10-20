/* Manual-only Crypto API test. Never installed or autoloaded. */
#include <linux/module.h>
#include <linux/crypto.h>
#include <linux/completion.h>
#include <linux/skbuff.h>
#include <linux/rtnetlink.h>
#include <crypto/aead.h>
#include <crypto/authenc.h>
#include <linux/ip.h>
#include <net/ip.h>

static char *target_driver;
module_param(target_driver, charp, 0444);
static bool only_sha256;
module_param(only_sha256, bool, 0444);
static unsigned int aesbits = 128;
module_param(aesbits, uint, 0444);
static unsigned int sha256_authsize = 16;
module_param(sha256_authsize, uint, 0444);
static unsigned int corrupt_part;
module_param(corrupt_part, uint, 0444);
static unsigned int esp_offset;
module_param(esp_offset, uint, 0444);
struct kat_storage {
    struct scatterlist assoc, data;
    unsigned char iv[16], plain[32];
};
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

static int check(const char *hash, unsigned int authsize, bool corrupt, bool encrypt)
{
    struct crypto_aead *sw, *hw;
    struct aead_request *enc = NULL, *dec = NULL;
    struct aead_givcrypt_request *hwenc = NULL;
    struct kat_storage *storage = NULL;
    struct scatterlist *assoc, *data;
    struct sk_buff *skb = NULL;
    char name[96], driver[96], reference[96];
    unsigned char key[RTA_SPACE(sizeof(struct crypto_authenc_key_param)) + 64];
    unsigned char *iv, *plain;
    unsigned char *buf;
    unsigned char prefix[20], guard[32];
    unsigned int saved_len;
    struct rtattr *rta = (void *)key;
    struct crypto_authenc_key_param *param;
    unsigned int i;
    unsigned int keylen = RTA_SPACE(sizeof(struct crypto_authenc_key_param)) +
                          (!strcmp(hash, "sha1") ? 20 : 32) + aesbits / 8;
    int err;

    snprintf(name, sizeof(name), "authenc(hmac(%s),cbc(aes))", hash);
    snprintf(driver, sizeof(driver), "authenc(hmac(%s-spu),cbc(aes-spu))", hash);
    snprintf(reference, sizeof(reference), "authenc(hmac(%s-generic),cbc(aes-generic))", hash);
    sw = crypto_alloc_aead(reference, 0, CRYPTO_ALG_ASYNC | CRYPTO_ALG_NEED_FALLBACK);
    if (IS_ERR(sw))
        return PTR_ERR(sw);
    hw = crypto_alloc_aead(target_driver ? target_driver : driver, 0, 0);
    if (IS_ERR(hw)) {
        err = PTR_ERR(hw);
        goto free_sw;
    }
    memset(key, 0, sizeof(key));
    rta->rta_type = CRYPTO_AUTHENC_KEYA_PARAM;
    rta->rta_len = RTA_LENGTH(sizeof(*param));
    param = RTA_DATA(rta);
    param->enckeylen = cpu_to_be32(aesbits / 8);
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
    storage = kzalloc(sizeof(*storage), GFP_KERNEL);
    if (!storage) { err = -ENOMEM; goto free_hw; }
    assoc = &storage->assoc;
    data = &storage->data;
    iv = storage->iv;
    plain = storage->plain;
    skb = alloc_skb(512, GFP_KERNEL);
    if (!skb) {
        err = -ENOMEM;
        goto free_hw;
    }
    skb_reserve(skb, 64);
    buf = skb_put(skb, esp_offset + 8 + 16 + 32 + authsize) + esp_offset;
    memset(skb->data, 0, skb->len);
    saved_len = skb->len;
    memset(guard, 0x5a, sizeof(guard));
    memcpy(skb->data + saved_len, guard, sizeof(guard));
    if (esp_offset) {
        struct iphdr *iph = (struct iphdr *)skb->data;
        iph->version = 4;
        iph->ihl = 5;
        iph->ttl = 64;
        iph->protocol = IPPROTO_ESP;
        iph->tot_len = htons(saved_len);
        iph->saddr = htonl(0xc6124501);
        iph->daddr = htonl(0xc6124502);
        ip_send_check(iph);
        memcpy(prefix, skb->data, sizeof(prefix));
    }
    buf[3] = 1; /* ESP SPI and sequence, no network configuration changes. */
    buf[7] = 1;
    for (i = 0; i < 16; i++)
        iv[i] = buf[8 + i] = (unsigned char)(i + 1);
    for (i = 0; i < 32; i++)
        plain[i] = buf[24 + i] = (unsigned char)(0x20 + i);
    /* Valid ESP trailer: two padding bytes, padlen, next-header. */
    plain[28] = buf[52] = 1;
    plain[29] = buf[53] = 2;
    plain[30] = buf[54] = 2;
    plain[31] = buf[55] = 4;
    sg_init_one(assoc, buf, 8);
    sg_init_one(data, buf + 24, 32 + authsize);
    enc = aead_request_alloc(sw, GFP_KERNEL);
    dec = aead_request_alloc(encrypt ? sw : hw, GFP_KERNEL);
    if (encrypt) hwenc = aead_givcrypt_alloc(hw, GFP_KERNEL);
    if (!enc || !dec || (encrypt && !hwenc)) {
        err = -ENOMEM;
        goto free_requests;
    }
    reinit_completion(&done);
    if (encrypt) {
        aead_givcrypt_set_callback(hwenc, 0, completed, skb);
        aead_givcrypt_set_assoc(hwenc, assoc, 8);
        aead_givcrypt_set_crypt(hwenc, data, data, 32, iv);
        aead_givcrypt_set_giv(hwenc, buf + 8, 1);
        hwenc->areq.next_hdr = 4;
        hwenc->areq.data_offset = esp_offset;
        err = finish(crypto_aead_givencrypt(hwenc));
    } else {
        aead_request_set_callback(enc, 0, completed, skb);
        aead_request_set_assoc(enc, assoc, 8);
        aead_request_set_crypt(enc, data, data, 32, iv);
        err = finish(crypto_aead_encrypt(enc));
    }
    if (err)
        goto free_requests;
    if (corrupt) {
        switch (corrupt_part) {
        case 0: buf[24 + 32] ^= 0x80; break;
        case 1: buf[0] ^= 0x80; break;
        case 2: buf[8] ^= 0x80; break;
        case 3: buf[24] ^= 0x80; break;
        default: err = -EINVAL; goto free_requests;
        }
    }
    reinit_completion(&done);
    aead_request_set_callback(dec, 0, completed, skb);
    aead_request_set_assoc(dec, assoc, 8);
    aead_request_set_crypt(dec, data, data, 32 + authsize, buf + 8);
    dec->data_offset = esp_offset;
    err = finish(crypto_aead_decrypt(dec));
    if (corrupt)
        err = err == -EBADMSG ? 0 : (err ? err : -EIO);
    else if (!err && memcmp(buf + 24, plain, 32))
        err = -EIO;
free_requests:
    if (!timed_out && skb &&
        (skb->len != saved_len ||
         memcmp(skb->data + saved_len, guard, sizeof(guard)) ||
         (esp_offset && memcmp(skb->data, prefix, sizeof(prefix))))) {
        pr_err("damson_spu_test: buffer boundary/header changed\n");
        err = -EOVERFLOW;
    }
    if (timed_out) {
        pr_err("damson_spu_test: timeout; retaining outstanding request; reboot needed before retry\n");
        return -ETIMEDOUT;
    }
    if (hwenc) aead_givcrypt_free(hwenc);
    aead_request_free(enc);
    aead_request_free(dec);
    kfree_skb(skb);
free_hw:
    kfree(storage);
    crypto_free_aead(hw);
free_sw:
    crypto_free_aead(sw);
    pr_info("damson_spu_test: AES%u/%s-%u %s %s: %s (%d)\n", aesbits, hash, authsize * 8, encrypt ? "encrypt" : "decrypt",
            corrupt ? "reject-tamper" : "decrypt", err ? "FAIL" : "PASS", err);
    return err;
}

static int __init test_init(void)
{
    int err;
    if (esp_offset != 0 && esp_offset != 20)
        return -EINVAL;
    if (aesbits != 128 && aesbits != 192 && aesbits != 256)
        return -EINVAL;
    err = check("sha256", sha256_authsize, false, false);
    if (!err) err = check("sha256", sha256_authsize, true, false);
    if (!err) err = check("sha256", sha256_authsize, false, true);
    if (!err) err = check("sha256", sha256_authsize, true, true);
    if (!err && !only_sha256) err = check("sha1", 12, false, false);
    if (!err && !only_sha256) err = check("sha1", 12, true, false);
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
