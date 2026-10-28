"""Build and verify staged IPKs against pinned original-firmware symbol inputs."""
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
from kernel_firmware import config_options, elf_module, sha, unresolved

ROOT = Path(__file__).resolve().parents[1]
INPUTS = ROOT / 'build/kernel-firmware-profiles'


def definitions():
    return json.loads((INPUTS / 'profiles.json').read_text())


def archive(files):
    output = io.BytesIO()
    with gzip.GzipFile(fileobj=output, mode='wb', filename='', mtime=0) as zipped:
        with tarfile.open(fileobj=zipped, mode='w') as tar:
            for name, data in sorted(files.items()):
                member = tarfile.TarInfo(name)
                member.mode, member.size = 0o644, len(data)
                tar.addfile(member, io.BytesIO(data))
    return output.getvalue()


def files(data):
    result = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as tar:
        for member in tar:
            if (not member.isfile() or member.name in result or member.name.startswith('/')
                    or '..' in Path(member.name).parts):
                raise ValueError('Unsafe or duplicate archive member')
            result[member.name] = tar.extractfile(member).read()
    return result


def expected_names():
    targets = (ROOT / 'build/vbntj/network-feed.modules').read_text().splitlines()
    names = {Path(t).stem for t in targets if t and not t.startswith('#')}
    return names - {'xt_nat'} | {'usbnet', 'cdc_ether', 'rndis_host', 'wireguard'}


def audit(profile, payloads):
    entry = definitions()[profile]
    if set(payloads) != expected_names() - set(entry['excluded_modules']) or len(payloads) != entry['module_count']:
        raise ValueError('Unexpected firmware candidate module set')
    modules = []
    for name, payload in sorted(payloads.items()):
        module = elf_module(payload)
        if module['modinfo']['vermagic'][0].strip() != entry['vermagic']:
            raise ValueError('Candidate vermagic mismatch: ' + name)
        module.pop('symbol_sizes')
        modules.append(dict(module, name=name))
    inputs = []
    for source in entry['stock_inputs']:
        directory = INPUTS / source
        provenance = json.loads((directory / 'source.json').read_text())
        data = (directory / 'stock-symbols.json.gz').read_bytes()
        if sha(data) != provenance['stock_symbols_sha256']:
            raise ValueError('Stock input checksum mismatch')
        stock = json.loads(gzip.decompress(data))
        config = gzip.decompress((directory / 'kernel.config.gz').read_bytes())
        if sha(config) != provenance['config_sha256'] or provenance['kernel_package'] != entry['kernel_package']:
            raise ValueError('Configuration or kernel ABI input mismatch')
        if config_options(config).get('CONFIG_MODVERSIONS') != 'n':
            raise ValueError('Versioned-symbol kernels need CRC verification')
        if unresolved(stock['stock_modules'], stock['exports']):
            raise ValueError('Original stock symbol closure failed')
        for module in modules:
            if set(module['exports']) & set(stock['exports']):
                raise ValueError('Candidate duplicates built-in kernel exports: ' + module['name'])
        provided = stock['exports'] + [symbol for m in stock['stock_modules'] for symbol in m['exports']]
        missing = unresolved(modules, provided)
        if missing:
            raise ValueError('Unresolved candidate imports for ' + source + ': ' + ', '.join(missing))
        inputs.append({'input': source, 'image_sha256': provenance['image_sha256'],
                       'config_sha256': provenance['config_sha256'], 'unresolved_symbols': []})
    return {'profile': profile, 'runtime_validated': False, 'modules': modules, 'firmware_checks': inputs,
            'limitations': 'Offline symbol closure does not verify all structure layouts or runtime behavior. '
                           'Modules are staged outside boot paths; manual device validation is required.'}


def package(profile, directory, output):
    entry = definitions()[profile]
    payloads = {path.stem: path.read_bytes() for path in directory.glob('*.ko')}
    report = audit(profile, payloads)
    result = {}
    for module in report['modules']:
        name = module['name']
        stem = name.replace('_', '-').lower()
        package_name = 'kmod-' + stem + '-' + profile.replace('4.1.52-', '') + '-4.1.52-candidate'
        filename = package_name + '_4.1.52-1_' + entry['architecture'] + '.ipk'
        staged = 'usr/lib/kernel-module-candidates/' + profile + '/' + name + '.ko'
        control = (f'Package: {package_name}\nVersion: 4.1.52-1\nArchitecture: {entry["architecture"]}\n'
                   f'Depends: kernel (= {entry["kernel_package"]})\nSection: kernel\nMaintainer: GUI_ipk\n'
                   f'Description: Offline-checked {name} candidate for {entry["device"]}; runtime validation required\n'
                   'X-Manual-Install-Only: yes\nX-Runtime-Validated: no\nX-Module-Staging-Only: yes\n'
                   'X-Offline-Symbol-Check: passed\n'
                   f'X-Kernel-Profile: {profile}\nX-Kernel-Vermagic: {entry["vermagic"]}\n'
                   f'X-Module-Path: /{staged}\n')
        blob = archive({'./debian-binary': b'2.0\n', './control.tar.gz': archive({'./control': control.encode()}),
                        './data.tar.gz': archive({'./' + staged: payloads[name]})})
        module.update(asset=filename, package=package_name, ipk_sha256=sha(blob), control=control)
        result['ipks/' + filename] = blob
    result['manifest.json'] = (json.dumps(report, indent=2, sort_keys=True) + '\n').encode()
    output.write_bytes(archive(result))
    return sha(output.read_bytes())


def restore(profile, destination):
    entry = definitions()[profile]
    data = (ROOT / entry['bundle']).read_bytes()
    if sha(data) != entry['bundle_sha256']:
        raise ValueError('Firmware candidate bundle checksum mismatch')
    bundle = files(data)
    report = json.loads(bundle.pop('manifest.json'))
    payloads = {}
    for module in report['modules']:
        name = module['name']
        raw = bundle.pop('ipks/' + module['asset'])
        if sha(raw) != module['ipk_sha256']:
            raise ValueError('Candidate IPK checksum mismatch')
        outer = files(raw)
        if set(outer) != {'./debian-binary', './control.tar.gz', './data.tar.gz'} or outer['./debian-binary'] != b'2.0\n':
            raise ValueError('Unexpected candidate package format')
        control = files(outer['./control.tar.gz'])
        if control != {'./control': module['control'].encode()}:
            raise ValueError('Unexpected candidate control scripts or fields')
        fields = dict(line.split(': ', 1) for line in module['control'].splitlines())
        expected = {'Depends': 'kernel (= ' + entry['kernel_package'] + ')', 'X-Module-Staging-Only': 'yes',
                    'X-Runtime-Validated': 'no', 'X-Kernel-Profile': profile, 'Architecture': entry['architecture'],
                    'X-Kernel-Vermagic': entry['vermagic']}
        if any(fields.get(k) != v for k, v in expected.items()):
            raise ValueError('Candidate profile metadata mismatch')
        staged = './usr/lib/kernel-module-candidates/' + profile + '/' + name + '.ko'
        payload = files(outer['./data.tar.gz'])
        if set(payload) != {staged} or fields.get('X-Module-Path') != staged[1:]:
            raise ValueError('Candidate payload outside staging directory')
        payloads[name] = payload[staged]
        destination.mkdir(parents=True, exist_ok=True)
        (destination / module['asset']).write_bytes(raw)
    if bundle:
        raise ValueError('Unexpected candidate bundle files')
    check = audit(profile, payloads)
    if check['firmware_checks'] != report['firmware_checks']:
        raise ValueError('Firmware audit input provenance differs')
    actual = {module['name']: module for module in check['modules']}
    for module in report['modules']:
        if any(module.get(key) != value for key, value in actual[module['name']].items()):
            raise ValueError('Candidate module evidence differs from payload')
    return report


def publication_records(work):
    from publication_layout import record
    rows = []
    for profile, entry in definitions().items():
        if not entry.get('bundle'):
            continue
        destination = work / profile
        report = restore(profile, destination)
        for module in report['modules']:
            path = destination / module['asset']
            stanza = module['control'] + 'Filename: ' + path.name + '\nSize: ' + str(path.stat().st_size) + '\nSHA256sum: ' + module['ipk_sha256']
            rows.append(record(path, stanza, entry['feed'], 'kernel', profile))
    return rows


def audit_vbntk_ipks(ipks):
    """Do not republish an existing-profile payload with unavailable imports."""
    if not ipks:
        raise ValueError('No VBNT-K IPKs to audit')
    directory = INPUTS / 'vbntk-2.4.5'
    source = json.loads((directory / 'source.json').read_text())
    raw = (directory / 'stock-symbols.json.gz').read_bytes()
    if sha(raw) != source['stock_symbols_sha256']:
        raise ValueError('VBNT-K stock input checksum mismatch')
    stock = json.loads(gzip.decompress(raw))
    modules = []
    for path in sorted(ipks):
        with tarfile.open(path, 'r:gz') as outer:
            data = outer.extractfile('./data.tar.gz').read()
        with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as tar:
            payloads = [tar.extractfile(m).read() for m in tar if m.isfile() and m.name.endswith('.ko')]
        if len(payloads) != 1:
            raise ValueError('Expected one existing-profile module per package')
        modules.append(dict(elf_module(payloads[0]), package=path.name))
    provided = stock['exports'] + [s for module in stock['stock_modules'] for s in module['exports']]
    missing = unresolved(modules, provided)
    if missing:
        raise ValueError('Unresolved VBNT-K module imports: ' + ', '.join(missing))
    return {'module_count': len(modules), 'unresolved_symbols': [], 'runtime_validation_performed': False,
            'original_image_sha256': source['image_sha256'],
            'modules': [{'package': m['package'], 'sha256': m['sha256']} for m in modules]}
