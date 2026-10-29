#!/usr/bin/env python
"""Inventory impl3 source interfaces; this is not a hardware capability test.

Compatible with Python 2.7 in the pinned SDK build container and Python 3.
"""
from __future__ import print_function
import argparse
import hashlib
import json
import os
import re


def code(text):
    return re.sub(r'/\*.*?\*/|//[^\n]*', '', text, flags=re.S)


def audit(sdk, module_source=None):
    module_source = module_source or os.path.join(
        sdk, 'bcmdrivers/opensource/char/spudd/impl3')
    paths = {
        'spu.c': os.path.join(module_source, 'spu.c'),
        'spu_runner.c': os.path.join(module_source, 'spu_runner.c'),
        'rdpa_ipsec_helper.h': os.path.join(
            sdk, 'rdp/drivers/rdpa_gpl/include/rdpa_ipsec_helper.h'),
    }
    sources, hashes = {}, {}
    for name, path in paths.items():
        with open(path, 'rb') as stream:
            raw = stream.read()
        hashes[name] = hashlib.sha256(raw).hexdigest()
        sources[name] = code(raw.decode('utf-8'))
    spu = sources['spu.c']
    helper = sources['rdpa_ipsec_helper.h']
    names = sorted(set(re.findall(r'\.cra_name\s*=\s*"([^"]+)"', spu)))
    auth_enum = re.search(r'typedef\s+enum\s*\{([^}]+)\}\s*rdpa_ipsec_auth_alg_e', helper)
    signature = re.search(r'\brdpa_ipsec_sa_desc_setting\s*\(([^)]+)\)', helper)
    if not names or not auth_enum or not signature:
        raise ValueError('Unrecognized impl3 source layout; inspect source manually')
    return {
        'format_version': 1,
        'scope': 'source-interface-inventory-only',
        'source_sha256': hashes,
        'registered_algorithms': names,
        'plain_cbc_aes_registered': 'cbc(aes)' in names,
        'aead_encrypt_callbacks': sorted(set(re.findall(r'\.encrypt\s*=\s*(\w+)', spu))),
        'aead_givencrypt_callbacks': sorted(set(re.findall(r'\.givencrypt\s*=\s*(\w+)', spu))),
        'runner_authentication_modes': re.findall(r'\brdpa_auth_alg_\w+', auth_enum.group(1)),
        'runner_descriptor_parameters': ' '.join(signature.group(1).split()),
        'hardware_plain_cbc_validation': 'not-established',
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sdk')
    parser.add_argument('--module-source')
    args = parser.parse_args()
    print(json.dumps(audit(args.sdk, args.module_source), indent=2, sort_keys=True))
