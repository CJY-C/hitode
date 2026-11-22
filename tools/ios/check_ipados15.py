"""Verify the extracted iPadOS 15.5 TrollStore app before uploading its IPA."""

import plistlib
import re
import subprocess
import sys
from pathlib import Path

TARGET = (15, 5, 0)


def version(value: str) -> tuple[int, ...]:
    parts = tuple(map(int, value.split('.')))
    return parts + (0,) * (3 - len(parts))


def check_app(app: Path) -> None:
    info = plistlib.loads((app / 'Info.plist').read_bytes())
    if version(info['MinimumOSVersion']) != TARGET or 2 not in info['UIDeviceFamily']:
        raise ValueError('expected a minimum OS of 15.5 and the iPad device family')

    executable = app / info['CFBundleExecutable']
    signed = plistlib.loads(subprocess.check_output(['ldid', '-e', executable]))
    for key in ('get-task-allow', 'com.apple.developer.kernel.increased-memory-limit',
                'com.apple.developer.kernel.extended-virtual-addressing'):
        if signed.get(key) is not True:
            raise ValueError(f'missing entitlement: {key}')

    helper = app / 'PlugIns/HitodeJIT.appex'
    binaries = {executable, *app.rglob('*.dylib')}
    for bundle in {helper, *app.rglob('*.appex'), *app.rglob('*.framework')}:
        metadata = plistlib.loads((bundle / 'Info.plist').read_bytes())
        if 'MinimumOSVersion' in metadata and version(metadata['MinimumOSVersion']) > TARGET:
            raise ValueError(f'{bundle.name} requires {metadata["MinimumOSVersion"]}')
        binaries.add(bundle / metadata['CFBundleExecutable'])

    for binary in sorted(binaries):
        build = subprocess.check_output(['xcrun', 'vtool', '-arch', 'arm64', '-show-build', binary],
                                        text=True)
        minimum = re.search(r'\bplatform IOS\s+minos ([\d.]+)', build)
        if minimum is None:
            minimum = re.search(r'\bLC_VERSION_MIN_IPHONEOS\s+cmdsize \d+\s+version ([\d.]+)', build)
        if minimum is None or version(minimum[1]) > TARGET:
            raise ValueError(f'{binary.name} needs an arm64 iOS deployment target at or below 15.5:\n{build}')
        print(f'{binary.relative_to(app)}: arm64 iOS {minimum[1]}')


if __name__ == '__main__':
    check_app(Path(sys.argv[1]))
