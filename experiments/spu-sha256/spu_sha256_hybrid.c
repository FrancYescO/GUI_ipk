/* Experimental SHA256-128 AEAD wrapper. Never installed or autoloaded.
 * Outer authentication is always HMAC-SHA256-128. Runner handles AES with
 * a private 96-bit framing layer, extended/verified in software.
 * Incoming SHA256 tags are checked BEFORE any hardware decryption.
 */
#include <linux/module.h>
#include <linux/crypto.h>
#include <linux/skbuff.h>
#include <linux/rtnetlink.h>
#include <crypto/aead.h>
#include <crypto/authenc.h>
#include <crypto/hash.h>
#include <crypto/algapi.h>
#include <crypto/scatterwalk.h>
#include <crypto/sha.h>
#include <crypto/aes.h>

static char *sha256_driver = "hmac(sha256-generic)";
module_param(sha256_driver, charp, 0444);
static bool private_sha1;
module_param(private_sha1, bool, 0444);
static atomic_t enc_packets = ATOMIC_INIT(0);
static atomic_t dec_packets = ATOMIC_INIT(0);
static atomic_t bad_tags = ATOMIC_INIT(0);
static int counter_get(char *buf, const struct kernel_param *kp)
{
    return scnprintf(buf, 32, "%d", atomic_read((atomic_t *)kp->arg));
}
static const struct kernel_param_ops counter_ops = { .get = counter_get };
module_param_cb(enc_packets, &counter_ops, &enc_packets, 0444);
module_param_cb(dec_packets, &counter_ops, &dec_packets, 0444);
module_param_cb(bad_tags, &counter_ops, &bad_tags, 0444);

struct hybrid_ctx {
    struct crypto_aead *runner[2];
    struct crypto_shash *sha256;
    struct crypto_shash *sha1;
};
struct hybrid_job {
    struct aead_request *outer;
    struct hybrid_ctx *ctx;
    struct sk_buff *skb;
    struct scatterlist assoc, payload;
    unsigned int plen;
    unsigned char iv[AES_BLOCK_SIZE];
    unsigned char *giv;
    bool encrypt;
    /* Must be last: underlying request context follows this structure. */
    struct aead_givcrypt_request inner;
};

static int hmac(struct crypto_shash *tfm, const u8 *p, unsigned int len, u8 *out)
{
    SHASH_DESC_ON_STACK(desc, tfm);
    desc->tfm = tfm;
    desc->flags = 0;
    return crypto_shash_digest(desc, p, len, out);
}

static int finish_job(struct hybrid_job *j, int err)
{
    u8 digest[SHA256_DIGEST_SIZE];
    u8 *data = j->skb->data;
    if (!err && j->encrypt) {
        err = hmac(j->ctx->sha256, data, 8 + AES_BLOCK_SIZE + j->plen, digest);
        if (!err && !private_sha1 &&
            crypto_memneq(data + 8 + AES_BLOCK_SIZE + j->plen, digest, 12))
            err = -EBADMSG;
        if (!err) {
            memcpy(data + 8 + AES_BLOCK_SIZE + j->plen, digest, 16);
            memcpy(j->giv, data + 8, AES_BLOCK_SIZE);
            scatterwalk_map_and_copy(data + 8 + AES_BLOCK_SIZE, j->outer->dst,
                                     0, j->plen + 16, 1);
            atomic_inc(&enc_packets);
        }
    } else if (!err) {
        scatterwalk_map_and_copy(data + 8 + AES_BLOCK_SIZE, j->outer->dst,
                                 0, j->plen, 1);
        atomic_inc(&dec_packets);
    }
    memzero_explicit(digest, sizeof(digest));
    kfree_skb(j->skb);
    kfree(j);
    return err;
}

static void hybrid_done(struct crypto_async_request *base, int err)
{
    struct aead_request *req = container_of(base, struct aead_request, base);
    struct aead_givcrypt_request *greq = container_of(req, struct aead_givcrypt_request, areq);
    struct hybrid_job *j = container_of(greq, struct hybrid_job, inner);
    struct aead_request *outer = j->outer;
    if (err == -EINPROGRESS)
        return;
    err = finish_job(j, err);
    aead_request_complete(outer, err);
}

static int hybrid_submit(struct aead_request *req, struct aead_givcrypt_request *greq)
{
    struct hybrid_ctx *ctx = crypto_aead_ctx(crypto_aead_reqtfm(req));
    struct hybrid_job *j;
    u8 digest[SHA256_DIGEST_SIZE], received[16];
    unsigned int plen, bytes;
    int err;
    bool enc = greq != NULL;
    if (req->assoclen != 8 || (!enc && req->cryptlen < 16))
        return -EINVAL;
    plen = req->cryptlen - (enc ? 0 : 16);
    if (!plen || (plen & (AES_BLOCK_SIZE - 1)) || plen > 16000)
        return -EINVAL;
    j = kzalloc(sizeof(*j) + crypto_aead_reqsize(ctx->runner[enc ? 0 : 1]), GFP_ATOMIC);
    if (!j)
        return -ENOMEM;
    bytes = 8 + AES_BLOCK_SIZE + plen;
    j->skb = alloc_skb(64 + bytes + SHA256_DIGEST_SIZE + 128, GFP_ATOMIC);
    if (!j->skb) {
        kfree(j);
        return -ENOMEM;
    }
    skb_reserve(j->skb, 64);
    skb_put(j->skb, bytes + 12); /* Runner's fixed-size private tag. */
    memset(j->skb->data, 0, bytes + SHA256_DIGEST_SIZE);
    j->outer = req;
    j->ctx = ctx;
    j->plen = plen;
    j->giv = enc ? greq->giv : NULL;
    j->encrypt = enc;
    scatterwalk_map_and_copy(j->skb->data, req->assoc, 0, 8, 0);
    scatterwalk_map_and_copy(j->skb->data + 24, req->src, 0, plen, 0);
    if (!enc) {
        memcpy(j->skb->data + 8, req->iv, AES_BLOCK_SIZE);
        scatterwalk_map_and_copy(received, req->src, plen, 16, 0);
        err = hmac(ctx->sha256, j->skb->data, bytes, digest);
        if (!err && crypto_memneq(digest, received, 16)) {
            atomic_inc(&bad_tags);
            err = -EBADMSG;
        }
        if (!err) {
            if (private_sha1)
                err = hmac(ctx->sha1, j->skb->data, bytes, digest);
            if (!err)
                memcpy(j->skb->data + bytes, digest, 12);
        }
        memzero_explicit(digest, sizeof(digest));
        if (err)
            return finish_job(j, err);
    }
    sg_init_one(&j->assoc, j->skb->data, 8);
    sg_init_one(&j->payload, j->skb->data + 24, plen + 12);
    aead_givcrypt_set_tfm(&j->inner, ctx->runner[enc ? 0 : 1]);
    aead_givcrypt_set_callback(&j->inner, 0, hybrid_done, j->skb);
    aead_givcrypt_set_assoc(&j->inner, &j->assoc, 8);
    aead_givcrypt_set_crypt(&j->inner, &j->payload, &j->payload,
                          plen + (enc ? 0 : 12), enc ? j->iv : j->skb->data + 8);
    j->inner.areq.next_hdr = req->next_hdr;
    j->inner.areq.data_offset = 0;
    if (enc) {
        aead_givcrypt_set_giv(&j->inner, j->skb->data + 8, greq->seq);
        err = crypto_aead_givencrypt(&j->inner);
    } else {
        err = crypto_aead_decrypt(&j->inner.areq);
    }
    if (err == -EINPROGRESS)
        return err;
    /* Runner returns EBUSY without queuing; never pretend it is pending. */
    if (err == -EBUSY)
        err = -ENOBUFS;
    return finish_job(j, err);
}
static int hybrid_enc(struct aead_givcrypt_request *req)
{
    return hybrid_submit(&req->areq, req);
}
static int hybrid_dec(struct aead_request *req)
{
    return hybrid_submit(req, NULL);
}
static int hybrid_authsize(struct crypto_aead *tfm, unsigned int size)
{
    return size == 16 ? 0 : -EINVAL;
}
static int hybrid_key(struct crypto_aead *tfm, const u8 *key, unsigned int keylen)
{
    struct hybrid_ctx *ctx = crypto_aead_ctx(tfm);
    struct crypto_authenc_keys keys;
    u8 innerkey[RTA_SPACE(sizeof(struct crypto_authenc_key_param)) + 32 + 32];
    struct rtattr *rta = (void *)innerkey;
    struct crypto_authenc_key_param *param = RTA_DATA(rta);
    unsigned int authbytes;
    int err = crypto_authenc_extractkeys(&keys, key, keylen);
    if (err || (keys.enckeylen != 16 && keys.enckeylen != 24 && keys.enckeylen != 32))
        return -EINVAL;
    if (!private_sha1 && keys.authkeylen > 32)
        return -EINVAL;
    authbytes = private_sha1 ? 20 : keys.authkeylen;
    memset(innerkey, 0, sizeof(innerkey));
    rta->rta_type = CRYPTO_AUTHENC_KEYA_PARAM;
    rta->rta_len = RTA_LENGTH(sizeof(*param));
    param->enckeylen = cpu_to_be32(keys.enckeylen);
    if (!private_sha1)
        memcpy(innerkey + RTA_SPACE(sizeof(*param)), keys.authkey, authbytes);
    memcpy(innerkey + RTA_SPACE(sizeof(*param)) + authbytes, keys.enckey, keys.enckeylen);
    err = crypto_shash_setkey(ctx->sha256, keys.authkey, keys.authkeylen);
    if (!err && private_sha1)
        err = crypto_shash_setkey(ctx->sha1, innerkey + RTA_SPACE(sizeof(*param)), 20);
    if (!err)
        err = crypto_aead_setkey(ctx->runner[0], innerkey,
                                RTA_SPACE(sizeof(*param)) + authbytes + keys.enckeylen);
    if (!err)
        err = crypto_aead_setkey(ctx->runner[1], innerkey,
                                RTA_SPACE(sizeof(*param)) + authbytes + keys.enckeylen);
    memzero_explicit(innerkey, sizeof(innerkey));
    return err;
}
static int hybrid_init(struct crypto_tfm *tfm)
{
    struct hybrid_ctx *ctx = crypto_tfm_ctx(tfm);
    int err;
    const char *runner_name = private_sha1 ?
        "authenc(hmac(sha1-spu),cbc(aes-spu))" :
        "authenc(hmac(sha256-spu),cbc(aes-spu))";
    ctx->sha1 = NULL;
    ctx->runner[0] = crypto_alloc_aead(runner_name, 0, 0);
    if (IS_ERR(ctx->runner[0]))
        return PTR_ERR(ctx->runner[0]);
    ctx->runner[1] = crypto_alloc_aead(runner_name, 0, 0);
    if (IS_ERR(ctx->runner[1])) {
        err = PTR_ERR(ctx->runner[1]);
        goto runner0;
    }
    ctx->sha256 = crypto_alloc_shash(sha256_driver, 0, 0);
    if (IS_ERR(ctx->sha256)) {
        err = PTR_ERR(ctx->sha256);
        goto runner1;
    }
    if (private_sha1) {
        ctx->sha1 = crypto_alloc_shash("hmac(sha1-generic)", 0, 0);
        if (IS_ERR(ctx->sha1)) {
            err = PTR_ERR(ctx->sha1);
            goto sha256;
        }
    }
    err = crypto_aead_setauthsize(ctx->runner[0], 12);
    if (!err)
        err = crypto_aead_setauthsize(ctx->runner[1], 12);
    if (!err)
        return 0;
    if (ctx->sha1) crypto_free_shash(ctx->sha1);
sha256:
    crypto_free_shash(ctx->sha256);
runner1:
    crypto_free_aead(ctx->runner[1]);
runner0:
    crypto_free_aead(ctx->runner[0]);
    return err;
}
static void hybrid_exit(struct crypto_tfm *tfm)
{
    struct hybrid_ctx *ctx = crypto_tfm_ctx(tfm);
    if (ctx->sha1) crypto_free_shash(ctx->sha1);
    crypto_free_shash(ctx->sha256);
    crypto_free_aead(ctx->runner[1]);
    crypto_free_aead(ctx->runner[0]);
}
static struct crypto_alg alg = {
    .cra_name = "authenc(hmac(sha256),cbc(aes))",
    .cra_driver_name = "authenc-hybrid-sha256-spu",
    .cra_priority = 4000,
    .cra_flags = CRYPTO_ALG_TYPE_AEAD | CRYPTO_ALG_ASYNC | CRYPTO_ALG_NEED_FALLBACK,
    .cra_blocksize = AES_BLOCK_SIZE,
    .cra_ctxsize = sizeof(struct hybrid_ctx),
    .cra_module = THIS_MODULE,
    .cra_type = &crypto_aead_type,
    .cra_init = hybrid_init,
    .cra_exit = hybrid_exit,
    .cra_aead = {
        .setkey = hybrid_key,
        .setauthsize = hybrid_authsize,
        .givencrypt = hybrid_enc,
        .decrypt = hybrid_dec,
        .geniv = "<built-in>",
        .ivsize = AES_BLOCK_SIZE,
        .maxauthsize = 16,
    },
};
static int __init init(void) { return crypto_register_alg(&alg); }
static void __exit fini(void) { crypto_unregister_alg(&alg); }
module_init(init);
module_exit(fini);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Lab-only AES Runner + software HMAC-SHA256-128 wrapper");
