#!/usr/bin/env python
"""Lab-only Runner IV/mode probe. Apply after the three stable SPU patches.

Private algorithm names prevent selection by production IPsec consumers.
No changes are made to public feed modules by this script.
"""
from __future__ import print_function
import os
import sys


def replace(text, old, new, count=1):
    if text.count(old) != count:
        raise ValueError('Unexpected source anchor: ' + old[:80])
    return text.replace(old, new)


root = sys.argv[1]
path = os.path.join(root, 'spu.c')
with open(path) as stream:
    source = stream.read()
# The fallback must still refer to the real, synchronous software algorithm.
source = replace(source, 'crypto_alloc_aead(alg->cra_name,',
                 'crypto_alloc_aead(alg->cra_name + 4,')
# An ECB request must never silently fall back to software CBC.
start = source.index('static void spu_aead_fallback_cipher_comp_enc')
end = source.index('static void spu_esp_crypt_done', start)
source = source[:start] + '''static int spu_aead_do_fallback_cipher(struct crypto_aead *aead,
                                       void *request, bool encrypt)
{
    return -EOPNOTSUPP;
}

''' + source[end:]
# Re-keying must replace, not OR together, the two key-length bit fields.
anchor = '    ctx->descAlg |= (authkeylen & BCM_DESC_AUTH_KEYLEN_MASK)'
source = replace(source, anchor, '''    ctx->descAlg &= ~((BCM_DESC_AUTH_KEYLEN_MASK << BCM_DESC_AUTH_KEYLEN_SHIFT) |
                      (BCM_DESC_ENCR_KEYLEN_MASK << BCM_DESC_ENCR_KEYLEN_SHIFT));
''' + anchor)
if not source.count('.cra_name = "') or not source.count('.cra_driver_name = "'):
    raise ValueError("Cannot privatize algorithm names")
source = source.replace('.cra_name = "', '.cra_name = "lab-')
source = source.replace('.cra_driver_name = "', '.cra_driver_name = "lab-')
with open(path, 'w') as stream:
    stream.write(source)
path = os.path.join(root, 'spu_runner.c')
with open(path) as stream:
    source = stream.read()
source = replace(source, 'static bdmf_object_handle ipsec_obj', '''
/* Descriptor-local probes: 0=baseline, 1=RNG clock disabled,
 * 2=plain mechanism, 3=both, 4=downstream AES encrypt. */
static unsigned int lab_mode;
module_param(lab_mode, uint, 0444);
MODULE_PARM_DESC(lab_mode, "LAB ONLY: Runner mode/IV capability probe 0..4");

int spu_cbc_lab_ready(void)
{
    return lab_mode == 2;
}
EXPORT_SYMBOL_GPL(spu_cbc_lab_ready);

unsigned int spu_cbc_lab_mode(void)
{
    return lab_mode;
}
EXPORT_SYMBOL_GPL(spu_cbc_lab_mode);

#define SPU_LAB_ENCRYPT_CTX 0x100U
int spu_cbc_lab_prepare_encrypt(struct crypto_aead *tfm)
{
    struct spu_ctx *ctx;
    if (lab_mode != 4 || !tfm || crypto_aead_tfm(tfm)->__crt_alg->cra_module != THIS_MODULE)
        return -EOPNOTSUPP;
    ctx = crypto_aead_ctx(tfm);
    if (ctx->direction != SPU_DIRECTION_INVALID || !(ctx->descAlg & BCM_DESC_ENCR_ALG_AES))
        return -EINVAL;
    ctx->descAlg |= SPU_LAB_ENCRYPT_CTX;
    return 0;
}
EXPORT_SYMBOL_GPL(spu_cbc_lab_prepare_encrypt);

static bdmf_object_handle ipsec_obj''')
source = replace(source, '    if ( 0 == rc )\n    {\n       cache_flush_len', '''
    if (lab_mode > 4)
       return -EINVAL;
    if (0 == rc && lab_mode) {
       if (lab_mode < 4 && (lab_mode & 1))
          RDD_IPSEC_SA_DESC_RNG_CLK_EN_WRITE(0, pSaDescr);
       if (lab_mode < 4 && (lab_mode & 2))
          RDD_IPSEC_SA_DESC_MECH_WRITE(IPSEC_RDB_MECH_PLAIN, pSaDescr);
       if (lab_mode == 4 && (pCtx->descAlg & SPU_LAB_ENCRYPT_CTX) &&
           pCtx->direction == SPU_DIRECTION_DS) {
          memcpy(pSaDescr->crypt_key, pCtx->encrypt_key, ekey_len);
          RDD_IPSEC_SA_DESC_DECRYPT_WRITE(0, pSaDescr);
       }
    }
    if ( 0 == rc )
    {
       cache_flush_len''')
with open(path, 'w') as stream:
    stream.write(source)
