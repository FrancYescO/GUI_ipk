/* GPL-2.0. Private CBC adapter correctness tests. No network configuration. */
#include <linux/module.h>
#include <linux/crypto.h>
#include <linux/completion.h>
#include <crypto/algapi.h>

static unsigned int max_len = 64;
module_param(max_len, uint, 0444);
static bool timed_out;
struct test_state {
    struct crypto_ablkcipher *hw;
    struct crypto_blkcipher *sw;
    struct ablkcipher_request *req;
    struct completion done;
    int result;
    u8 *plain, *input, *output, *expected;
    u8 iv[16], original_iv[16], sw_iv[16];
    struct scatterlist src[2], dst[2], swsrc, swdst;
};

static void completed(struct crypto_async_request *base, int err)
{
    struct test_state *t = base->data;
    if (err == -EINPROGRESS)
        return;
    t->result = err;
    complete(&t->done);
}
static int wait_result(struct test_state *t, int err)
{
    if (err != -EINPROGRESS)
        return err;
    if (!wait_for_completion_timeout(&t->done, 10 * HZ)) {
        timed_out = true;
        __module_get(THIS_MODULE);
        pr_err("spu_cbc_kat: PENDING; retaining requests and buffers; do not stop/unload\n");
        return -ETIMEDOUT;
    }
    return t->result;
}

static int check(struct test_state *t, unsigned int keylen, unsigned int len, bool inplace)
{
    struct blkcipher_desc desc;
    unsigned int i;
    int err;
    for (i = 0; i < len; i++)
        t->plain[i] = t->input[i] = (i * 31 + len + keylen) & 255;
    for (i = 0; i < 16; i++)
        t->iv[i] = t->original_iv[i] = t->sw_iv[i] = i + len + inplace;
    sg_init_one(&t->swsrc, t->plain, len);
    sg_init_one(&t->swdst, t->expected, len);
    memset(&desc, 0, sizeof(desc));
    desc.tfm = t->sw;
    desc.info = t->sw_iv;
    err = crypto_blkcipher_encrypt_iv(&desc, &t->swdst, &t->swsrc, len);
    if (err)
        return err;
    sg_init_table(t->src, 2);
    sg_set_buf(t->src, t->input, 5);
    sg_set_buf(t->src + 1, t->input + 5, len - 5);
    sg_init_table(t->dst, 2);
    sg_set_buf(t->dst, t->output, 13);
    sg_set_buf(t->dst + 1, t->output + 13, len - 13);
    reinit_completion(&t->done);
    ablkcipher_request_set_crypt(t->req, t->src, inplace ? t->src : t->dst, len, t->iv);
    err = wait_result(t, crypto_ablkcipher_encrypt(t->req));
    if (err) {
        pr_err("spu_cbc_kat: encrypt returned %d\n", err);
        return err;
    }
    if (memcmp(inplace ? t->input : t->output, t->expected, len) ||
        memcmp(t->iv, t->expected + len - 16, 16))
    {
        pr_err("spu_cbc_kat: encrypt ciphertext/IV mismatch\n");
        return -EBADMSG;
    }
    memcpy(t->input, t->expected, len);
    memcpy(t->iv, t->original_iv, 16);
    reinit_completion(&t->done);
    ablkcipher_request_set_crypt(t->req, t->src, inplace ? t->src : t->dst, len, t->iv);
    err = wait_result(t, crypto_ablkcipher_decrypt(t->req));
    if (!err && (memcmp(inplace ? t->input : t->output, t->plain, len) ||
                 memcmp(t->iv, t->expected + len - 16, 16)))
        err = -EBADMSG;
    pr_info("spu_cbc_kat: AES%u len=%u inplace=%d: %s (%d)\n",
            keylen * 8, len, inplace, err ? "FAIL" : "PASS", err);
    return err;
}

static int __init kat_init(void)
{
    struct test_state *t;
    static const unsigned int lengths[] = { 16, 32, 64, 1504, 16016 };
    static const unsigned int keys[] = { 16, 24, 32, 16 };
    u8 key[32];
    unsigned int i, k, n, inplace;
    int err = -ENOMEM;
    if (max_len < 16 || max_len > 16016)
        return -EINVAL;
    t = kzalloc(sizeof(*t), GFP_KERNEL);
    if (!t)
        return -ENOMEM;
    init_completion(&t->done);
    t->plain = kmalloc(max_len, GFP_KERNEL);
    t->input = kmalloc(max_len, GFP_KERNEL);
    t->output = kmalloc(max_len, GFP_KERNEL);
    t->expected = kmalloc(max_len, GFP_KERNEL);
    t->hw = crypto_alloc_ablkcipher("spu-cbc-lab", 0, 0);
    t->sw = crypto_alloc_blkcipher("cbc(aes-generic)", 0, 0);
    pr_info("spu_cbc_kat: allocate hw=%d sw=%d\n",
            IS_ERR(t->hw) ? (int)PTR_ERR(t->hw) : 0,
            IS_ERR(t->sw) ? (int)PTR_ERR(t->sw) : 0);
    if (!t->plain || !t->input || !t->output || !t->expected || IS_ERR(t->hw) || IS_ERR(t->sw))
        goto cleanup;
    t->req = ablkcipher_request_alloc(t->hw, GFP_KERNEL);
    if (!t->req)
        goto cleanup;
    ablkcipher_request_set_callback(t->req, 0, completed, t);
    for (k = 0; k < ARRAY_SIZE(keys); k++) {
        for (i = 0; i < sizeof(key); i++)
            key[i] = i + 7 * k;
        err = crypto_ablkcipher_setkey(t->hw, key, keys[k]);
        if (!err)
            err = crypto_blkcipher_setkey(t->sw, key, keys[k]);
        if (err)
            goto cleanup;
        for (n = 0; n < ARRAY_SIZE(lengths); n++) {
            if (lengths[n] > max_len)
                continue;
            for (inplace = 0; inplace < 2; inplace++) {
                err = check(t, keys[k], lengths[n], inplace);
                if (err)
                    goto cleanup;
            }
        }
    }
    ablkcipher_request_set_crypt(t->req, t->src, t->dst, 15, t->iv);
    err = crypto_ablkcipher_encrypt(t->req);
    if (err != -EINVAL) { err = -EIO; goto cleanup; }
    ablkcipher_request_set_crypt(t->req, t->src, t->dst, 0, t->iv);
    err = crypto_ablkcipher_encrypt(t->req);
    if (err) goto cleanup;
    pr_info("spu_cbc_kat: ALL PASS\n");
cleanup:
    pr_info("spu_cbc_kat: result=%d\n", err);
    memzero_explicit(key, sizeof(key));
    if (timed_out)
        return 0;
    ablkcipher_request_free(t->req);
    if (!IS_ERR_OR_NULL(t->hw)) crypto_free_ablkcipher(t->hw);
    if (!IS_ERR_OR_NULL(t->sw)) crypto_free_blkcipher(t->sw);
    kfree(t->plain); kfree(t->input); kfree(t->output); kfree(t->expected); kfree(t);
    return err;
}
static void __exit kat_exit(void) { }
module_init(kat_init);
module_exit(kat_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Private SPU CBC comparison with software AES128/192/256 and IV checks");
