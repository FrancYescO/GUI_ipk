/* GPL-2.0. Experimental CBC provider over private SPU Runner requests.
 * No public CBC name is registered. Not installed, packaged or autoloaded.
 * Private ESP framing/HMAC is discarded; it is not application authentication.
 */
#include <linux/module.h>
#include <linux/crypto.h>
#include <linux/skbuff.h>
#include <linux/rtnetlink.h>
#include <linux/random.h>
#include <crypto/aead.h>
#include <crypto/authenc.h>
#include <crypto/hash.h>
#include <crypto/algapi.h>
#include <crypto/internal/skcipher.h>
#include <crypto/scatterwalk.h>
#include <crypto/aes.h>
#include <crypto/sha.h>

extern unsigned int spu_cbc_lab_mode(void);
extern int spu_cbc_lab_prepare_encrypt(struct crypto_aead *tfm);
static char *hash_driver = "hmac(sha1)";
module_param(hash_driver, charp, 0444);
MODULE_PARM_DESC(hash_driver, "Framing HMAC: generic SHA1 or explicitly selected private ARM SHA1");
static atomic_t enc_chunks = ATOMIC_INIT(0), dec_chunks = ATOMIC_INIT(0);
static int counter_get(char *buf, const struct kernel_param *kp)
{
    return scnprintf(buf, 32, "%d", atomic_read((atomic_t *)kp->arg));
}
static const struct kernel_param_ops counter_ops = { .get = counter_get };
module_param_cb(enc_chunks, &counter_ops, &enc_chunks, 0444);
module_param_cb(dec_chunks, &counter_ops, &dec_chunks, 0444);

struct cbc_ctx {
    struct crypto_aead *runner[2];
    struct crypto_cipher *pad_aes;
    struct crypto_shash *hmac;
    u8 authkey[20];
    atomic_t busy;
    bool keyed;
    bool native;
};
struct cbc_job {
    struct ablkcipher_request *outer;
    struct cbc_ctx *ctx;
    struct sk_buff *skb;
    unsigned int offset, chunk;
    bool encrypt;
    u8 chain[16];
    u8 next_iv[16];
    struct scatterlist assoc, payload;
    /* Must be last: the backend request context follows. */
    struct aead_givcrypt_request inner;
};
static int submit_chunk(struct cbc_job *j);

static int hmac_frame(struct cbc_ctx *ctx, u8 *data, unsigned int bytes, u8 *tag)
{
    SHASH_DESC_ON_STACK(desc, ctx->hmac);
    u8 digest[SHA1_DIGEST_SIZE];
    int err;
    desc->tfm = ctx->hmac;
    desc->flags = 0;
    err = crypto_shash_digest(desc, data, bytes, digest);
    if (!err)
        memcpy(tag, digest, 12);
    memzero_explicit(digest, sizeof(digest));
    return err;
}

static void finish_job(struct cbc_job *j, int err)
{
    struct ablkcipher_request *outer = j->outer;
    struct cbc_ctx *ctx = j->ctx;
    if (!err)
        memcpy(outer->info, j->chain, 16);
    kfree_skb(j->skb);
    memzero_explicit(j->chain, sizeof(j->chain));
    kfree(j);
    atomic_set(&ctx->busy, 0);
    ablkcipher_request_complete(outer, err);
}

static int consume_chunk(struct cbc_job *j, int err)
{
    u8 *data;
    u8 original[16], block[16];
    unsigned int i, n;
    if (err)
        return err;
    data = j->skb->data + 24;
    atomic_inc(j->encrypt ? &enc_chunks : &dec_chunks);
    if (j->ctx->native) {
        memcpy(j->chain, j->encrypt ? data + j->chunk - 16 : j->next_iv, 16);
        scatterwalk_map_and_copy(data, j->outer->dst, j->offset, j->chunk, 1);
        j->offset += j->chunk;
        return 0;
    }
    if (j->encrypt) {
        memcpy(j->chain, data, 16);
        scatterwalk_map_and_copy(data, j->outer->dst, j->offset, 16, 1);
    } else {
        for (n = 0; n < j->chunk; n += 16) {
            /* Read ciphertext before writing when source == destination. */
            scatterwalk_map_and_copy(original, j->outer->src, j->offset + n, 16, 0);
            for (i = 0; i < 16; i++)
                block[i] = data[n + i] ^ j->chain[i];
            memcpy(j->chain, original, 16);
            scatterwalk_map_and_copy(block, j->outer->dst, j->offset + n, 16, 1);
        }
    }
    j->offset += j->chunk;
    return 0;
}

static void inner_done(struct crypto_async_request *base, int err)
{
    struct aead_request *req = container_of(base, struct aead_request, base);
    struct aead_givcrypt_request *greq = container_of(req, struct aead_givcrypt_request, areq);
    struct cbc_job *j = container_of(greq, struct cbc_job, inner);
    if (err == -EINPROGRESS)
        return;
    err = consume_chunk(j, err);
    while (!err && j->offset < j->outer->nbytes) {
        err = submit_chunk(j);
        if (err == -EINPROGRESS)
            return;
        err = consume_chunk(j, err);
    }
    finish_job(j, err);
}

static int submit_chunk(struct cbc_job *j)
{
    struct crypto_aead *backend = j->ctx->runner[j->encrypt ? 0 : 1];
    unsigned int bytes, i;
    u8 *frame, *padding;
    int err;
    kfree_skb(j->skb);
    j->skb = NULL;
    j->chunk = j->encrypt && !j->ctx->native ? 16 :
        min_t(unsigned int, 16000, j->outer->nbytes - j->offset);
    bytes = 24 + j->chunk + (j->ctx->native ? 0 : 16);
    j->skb = alloc_skb(64 + bytes + 12 + 128, GFP_ATOMIC);
    if (!j->skb)
        return -ENOMEM;
    skb_reserve(j->skb, 64);
    frame = skb_put(j->skb, bytes + 12);
    memset(frame, 0, bytes + 12);
    frame[3] = frame[7] = 1;
    scatterwalk_map_and_copy(frame + 24, j->outer->src, j->offset, j->chunk, 0);
    if (j->ctx->native) {
        memcpy(frame + 8, j->chain, 16);
        if (!j->encrypt)
            memcpy(j->next_iv, frame + 24 + j->chunk - 16, 16);
        err = hmac_frame(j->ctx, frame, bytes, frame + bytes);
        if (err)
            return err;
    } else {
        if (j->encrypt)
            for (i = 0; i < 16; i++)
                frame[24 + i] ^= j->chain[i];
        padding = frame + 24 + j->chunk;
        for (i = 0; i < 14; i++)
            padding[i] = i + 1;
        padding[14] = 14;
        padding[15] = 4;
        if (!j->encrypt) {
            /* The synthetic trailer is independent of CBC payload blocks in ECB. */
            crypto_cipher_encrypt_one(j->ctx->pad_aes, padding, padding);
            err = hmac_frame(j->ctx, frame, bytes, frame + bytes);
            if (err)
                return err;
        }
    }
    sg_init_one(&j->assoc, frame, 8);
    sg_init_one(&j->payload, frame + 24, bytes - 24 + 12);
    aead_givcrypt_set_tfm(&j->inner, backend);
    aead_givcrypt_set_callback(&j->inner, 0, inner_done, j->skb);
    aead_givcrypt_set_assoc(&j->inner, &j->assoc, 8);
    aead_givcrypt_set_crypt(&j->inner, &j->payload, &j->payload,
                          bytes - 24 + (j->encrypt && !j->ctx->native ? 0 : 12), frame + 8);
    j->inner.areq.next_hdr = 4;
    j->inner.areq.data_offset = 0;
    if (j->encrypt && !j->ctx->native) {
        aead_givcrypt_set_giv(&j->inner, frame + 8, 1);
        err = crypto_aead_givencrypt(&j->inner);
    } else {
        err = crypto_aead_decrypt(&j->inner.areq);
    }
    /* The vendor never queues on EBUSY. Do not tell callers to await it. */
    return err == -EBUSY ? -ENOBUFS : err;
}

static int cbc_submit(struct ablkcipher_request *req, bool encrypt)
{
    struct cbc_ctx *ctx = crypto_ablkcipher_ctx(crypto_ablkcipher_reqtfm(req));
    struct cbc_job *j;
    unsigned int size;
    int err;
    if (req->nbytes & 15)
        return -EINVAL;
    if (!ctx->keyed)
        return -ENOKEY;
    if (!req->nbytes)
        return 0;
    if (atomic_cmpxchg(&ctx->busy, 0, 1))
        return -ENOBUFS;
    size = max(crypto_aead_reqsize(ctx->runner[0]), crypto_aead_reqsize(ctx->runner[1]));
    j = kzalloc(sizeof(*j) + size, GFP_ATOMIC);
    if (!j) {
        atomic_set(&ctx->busy, 0);
        return -ENOMEM;
    }
    j->outer = req;
    j->ctx = ctx;
    j->encrypt = encrypt;
    memcpy(j->chain, req->info, 16);
    do {
        err = submit_chunk(j);
        if (err == -EINPROGRESS)
            return err;
        err = consume_chunk(j, err);
    } while (!err && j->offset < req->nbytes);
    if (!err)
        memcpy(req->info, j->chain, 16);
    kfree_skb(j->skb);
    kfree(j);
    atomic_set(&ctx->busy, 0);
    return err;
}
static int cbc_encrypt(struct ablkcipher_request *req) { return cbc_submit(req, true); }
static int cbc_decrypt(struct ablkcipher_request *req) { return cbc_submit(req, false); }

static int cbc_setkey(struct crypto_ablkcipher *tfm, const u8 *key, unsigned int len)
{
    struct cbc_ctx *ctx = crypto_ablkcipher_ctx(tfm);
    u8 blob[RTA_SPACE(sizeof(struct crypto_authenc_key_param)) + 20 + 32];
    struct rtattr *rta = (void *)blob;
    struct crypto_authenc_key_param *param = RTA_DATA(rta);
    int err;
    if (len != 16 && len != 24 && len != 32)
        return -EINVAL;
    if (atomic_cmpxchg(&ctx->busy, 0, 1))
        return -ENOBUFS;
    ctx->keyed = false;
    memset(blob, 0, sizeof(blob));
    rta->rta_type = CRYPTO_AUTHENC_KEYA_PARAM;
    rta->rta_len = RTA_LENGTH(sizeof(*param));
    param->enckeylen = cpu_to_be32(len);
    memcpy(blob + RTA_SPACE(sizeof(*param)), ctx->authkey, 20);
    memcpy(blob + RTA_SPACE(sizeof(*param)) + 20, key, len);
    err = crypto_aead_setkey(ctx->runner[0], blob, RTA_SPACE(sizeof(*param)) + 20 + len);
    if (!err)
        err = crypto_aead_setkey(ctx->runner[1], blob, RTA_SPACE(sizeof(*param)) + 20 + len);
    if (!err)
        err = crypto_cipher_setkey(ctx->pad_aes, key, len);
    if (!err)
        ctx->keyed = true;
    memzero_explicit(blob, sizeof(blob));
    atomic_set(&ctx->busy, 0);
    return err;
}

static void cbc_exit(struct crypto_tfm *tfm)
{
    struct cbc_ctx *ctx = crypto_tfm_ctx(tfm);
    if (!IS_ERR_OR_NULL(ctx->runner[0])) crypto_free_aead(ctx->runner[0]);
    if (!IS_ERR_OR_NULL(ctx->runner[1])) crypto_free_aead(ctx->runner[1]);
    if (!IS_ERR_OR_NULL(ctx->pad_aes)) crypto_free_cipher(ctx->pad_aes);
    if (!IS_ERR_OR_NULL(ctx->hmac)) crypto_free_shash(ctx->hmac);
    memzero_explicit(ctx->authkey, sizeof(ctx->authkey));
}
static int cbc_init(struct crypto_tfm *tfm)
{
    struct cbc_ctx *ctx = crypto_tfm_ctx(tfm);
    const char *name = "lab-authenc(hmac(sha1-spu),cbc(aes-spu))";
    int i, err;
    memset(ctx, 0, sizeof(*ctx));
    ctx->native = spu_cbc_lab_mode() == 4;
    atomic_set(&ctx->busy, 0);
    for (i = 0; i < 2; i++) {
        ctx->runner[i] = crypto_alloc_aead(name, 0, 0);
        if (IS_ERR(ctx->runner[i])) {
            err = PTR_ERR(ctx->runner[i]);
            goto fail;
        }
        err = crypto_aead_setauthsize(ctx->runner[i], 12);
        if (err) goto fail;
    }
    if (ctx->native) {
        err = spu_cbc_lab_prepare_encrypt(ctx->runner[0]);
        if (err) goto fail;
    }
    ctx->pad_aes = crypto_alloc_cipher("aes-generic", 0, 0);
    if (IS_ERR(ctx->pad_aes)) { err = PTR_ERR(ctx->pad_aes); goto fail; }
    ctx->hmac = crypto_alloc_shash(hash_driver, 0, CRYPTO_ALG_ASYNC | CRYPTO_ALG_NEED_FALLBACK);
    if (IS_ERR(ctx->hmac)) { err = PTR_ERR(ctx->hmac); goto fail; }
    if (crypto_shash_digestsize(ctx->hmac) != SHA1_DIGEST_SIZE) { err = -EINVAL; goto fail; }
    get_random_bytes(ctx->authkey, sizeof(ctx->authkey));
    err = crypto_shash_setkey(ctx->hmac, ctx->authkey, sizeof(ctx->authkey));
    if (!err) return 0;
fail:
    cbc_exit(tfm);
    return err;
}

static struct crypto_alg algorithm = {
    .cra_name = "spu-cbc-lab",
    .cra_driver_name = "spu-cbc-native-lab",
    .cra_priority = 100,
    .cra_flags = CRYPTO_ALG_TYPE_ABLKCIPHER | CRYPTO_ALG_ASYNC | CRYPTO_ALG_KERN_DRIVER_ONLY,
    .cra_blocksize = 16,
    .cra_ctxsize = sizeof(struct cbc_ctx),
    .cra_type = &crypto_ablkcipher_type,
    .cra_module = THIS_MODULE,
    .cra_init = cbc_init,
    .cra_exit = cbc_exit,
    .cra_u.ablkcipher = {
        .min_keysize = 16, .max_keysize = 32, .ivsize = 16,
        .setkey = cbc_setkey, .encrypt = cbc_encrypt, .decrypt = cbc_decrypt,
        .geniv = "eseqiv",
    },
};
static int __init lab_init(void)
{
    if (spu_cbc_lab_mode() != 2 && spu_cbc_lab_mode() != 4)
        return -EOPNOTSUPP;
    if (strcmp(hash_driver, "hmac(sha1)") && strcmp(hash_driver, "hmac(sha1-generic)") &&
        strcmp(hash_driver, "hmac(sha1-spu-cbc-lab-arm)"))
        return -EINVAL;
    if (spu_cbc_lab_mode() == 2)
        strlcpy(algorithm.cra_driver_name, "spu-cbc-ecb-lab", sizeof(algorithm.cra_driver_name));
    return crypto_register_alg(&algorithm);
}
static void __exit lab_exit(void) { crypto_unregister_alg(&algorithm); }
module_init(lab_init);
module_exit(lab_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Private experimental AES-CBC provider over SPU Runner, modes 2/4");
