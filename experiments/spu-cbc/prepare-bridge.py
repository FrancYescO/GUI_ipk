#!/usr/bin/env python
"""Private identity and CBC selector for the already-patched cryptodev 1.14."""
from __future__ import print_function
import os
import sys

root = sys.argv[1]
path = os.path.join(root, 'Makefile')
with open(path) as stream:
    source = stream.read()
assert 'cryptodev-objs =' in source and 'obj-m += cryptodev.o' in source
source = source.replace('cryptodev-objs =', 'cryptodev_cbc_lab-objs =')
source = source.replace('obj-m += cryptodev.o', 'obj-m += cryptodev_cbc_lab.o')
with open(path, 'w') as stream:
    stream.write(source)
path = os.path.join(root, 'ioctl.c')
with open(path) as stream:
    source = stream.read()
assert source.count('alg_name = "cbc(aes)";') == 1
source = source.replace('alg_name = "cbc(aes)";', 'alg_name = cbc_driver;')
anchor = 'tfm = cryptodev_crypto_blkcipher_tfm(ses_ptr->cdata.async.s);'
assert source.count(anchor) == 1
# 4.1's default geniv wrapper drops KERN_DRIVER_ONLY. Report the transform
# actually selected by ablkcipher_request_set_tfm(), not its IV wrapper.
source = source.replace(anchor, '''tfm = crypto_ablkcipher_tfm(
                crypto_ablkcipher_crt(ses_ptr->cdata.async.s)->base);''')
assert source.count('switch (sop->cipher)') == 1
source = source.replace('switch (sop->cipher)', '''if (sop->cipher != CRYPTO_AES_CBC || sop->mac)
        return -EOPNOTSUPP;
    switch (sop->cipher)''')
assert source.count('kcop->mm = current->mm;') == 1
source = source.replace('kcop->mm = current->mm;', '''kcop->mm = NULL;
    /* Copy-only lab bridge: no get_user_pages or task_struct mm layout. */
    kcop->cop.flags |= COP_FLAG_NO_ZC;''')
assert '.name = "crypto",' in source
source = source.replace('.name = "crypto",', '.name = "crypto-cbc-lab",')
# Locate the misc-device initializer without depending on tab alignment.
start = source.index('static struct miscdevice cryptodev =')
before, tail = source[:start], source[start:]
import re
tail, count = re.subn(r'\.minor\s*=\s*[^,]+,', '.minor = MISC_DYNAMIC_MINOR,', tail, count=1)
assert count == 1
tail, count = re.subn(r'\.mode\s*=\s*[^,]+,', '.mode = 0600,', tail, count=1)
assert count == 1
source = before + tail
anchor = 'static struct miscdevice cryptodev ='
# Parameter must precede cryptodev_create_session(), which consumes it.
position = re.search(r'static\s+int\s+crypto_create_session\s*\(', source).start()
source = source[:position] + '''static char *cbc_driver = "cbc(aes-generic)";
module_param(cbc_driver, charp, 0444);
MODULE_PARM_DESC(cbc_driver, "LAB ONLY: CBC provider for private test device");

''' + source[position:]
source = re.sub(r'MODULE_ALIAS\([^\n]+\);', '', source)
with open(path, 'w') as stream:
    stream.write(source)
path = os.path.join(root, 'authenc.c')
with open(path) as stream:
    source = stream.read()
assert 'kcaop->mm = current->mm;' in source
source = source.replace('kcaop->mm = current->mm;', 'kcaop->mm = NULL;')
with open(path, 'w') as stream:
    stream.write(source)
path = os.path.join(root, 'zc.c')
with open(path) as stream:
    source = stream.read()
assert source.count('struct scatterlist *sgp;') == 1
source = source.replace('struct scatterlist *sgp;', '''struct scatterlist *sgp;

    if (!mm)
        return -EOPNOTSUPP;''')
source = source.replace('current->mm', 'NULL')
with open(path, 'w') as stream:
    stream.write(source)
path = os.path.join(root, 'cryptodev_int.h')
with open(path) as stream:
    source = stream.read()
assert 'current->comm, current->pid,' in source
source = source.replace('current->comm, current->pid,', '"cryptodev-cbc-lab", 0,')
with open(path, 'w') as stream:
    stream.write(source)
