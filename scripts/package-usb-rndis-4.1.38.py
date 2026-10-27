#!/usr/bin/env python3
"""Package the exact USB replacement pairs tested on their 4.1.38 runtime ABI."""
import argparse
import hashlib
from pathlib import Path
import runpy


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--profile', choices=['vbnto', 'vbnts'], required=True)
    args = parser.parse_args()
    packager = runpy.run_path(str(Path(__file__).with_name('package-vbnto-4.1.38.py')))
    config = packager['profile_config'](args.profile)
    modules = config['USB_MODULES']
    if set(modules) != {'cdc_ether', 'rndis_host'}:
        raise ValueError('Expected both validated USB drivers')
    payloads = {name: (args.source / (name + '.ko')).read_bytes() for name in modules}
    for name, payload in payloads.items():
        if hashlib.sha256(payload).hexdigest() != modules[name]:
            raise ValueError('Payload differs from runtime test: ' + name)
    args.output.mkdir(parents=True, exist_ok=True)
    archive = packager['archive']
    for name, payload in payloads.items():
        package = 'kmod-' + name.replace('_', '-') + '-' + args.profile + '-4.1.38-manual'
        control = (f'Package: {package}\nVersion: 4.1.38-1\nArchitecture: arm_cortex-a9\n'
                   'Section: kernel\nMaintainer: GUI_ipk\n'
                   f'Depends: kernel (= {config["KERNEL"]})\n'
                   f'Description: Manual {name} RNDIS compatibility driver for {config["TARGET"]}\n'
                   f'X-Firmware: {config["FIRMWARE"]}\nX-Kernel-Vermagic: {config["VERMAGIC"]}\n'
                   'X-Manual-Install-Only: yes\n'
                   'X-Required-Loaded-Modules: usbnet (native firmware module)\n'
                   'X-Required-Driver-Pair: cdc_ether, rndis_host\n'
                   'X-Runtime-Test: load-unload-driver-registration\n'
                   'X-USB-Traffic-Tested: no\n').encode()
        ipk = archive([('debian-binary', b'2.0\n', 0o644),
                       ('control.tar.gz', archive([('control', control, 0o644)]), 0o644),
                       ('data.tar.gz', archive([('lib/modules/4.1.38/' + name + '.ko', payload, 0o644)]), 0o644)])
        (args.output / (package + '_4.1.38-1_arm_cortex-a9.ipk')).write_bytes(ipk)
    sums = [hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + p.name
            for p in sorted(args.output.glob('*.ipk'))]
    (args.output / 'SHA256SUMS').write_text('\n'.join(sums) + '\n')


if __name__ == '__main__':
    main()
