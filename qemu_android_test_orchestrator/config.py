import json
import os
from _warnings import warn
from typing import TypeVar, Dict, Tuple, Callable

T = TypeVar('T')

_default_cfg = {
    'job_workdir': None,
    'job_command': './gradlew connectedAndroidTest',
    'virtwifi_hack': True,
    'virtwificonnector_apk': 'virtwificonnector-debug.apk',
    'permission_approve': True,
    'qemu_workdir': None,
    'qemu_bin': f'qemu-system-{os.uname().machine}',
    'qemu_debug': False,
    'qemu_args': [
        # CPU
        '-enable-kvm', '-smp', '2', '-cpu', 'host',

        # RAM
        '-m', '2048',

        # Linux
        '-kernel', 'kernel',
        '-append', 'root=/dev/ram0 androidboot.selinux=permissive androidboot.hardware=android_x86_64 console=ttyS0 '
                   'RAMDISK=vdb SETUPWIZARD=0',
        '-initrd', 'initrd.img',

        # Generic hardware
        '-soundhw', 'ac97',
        '-netdev', 'user,id=network,hostfwd=tcp::5555-:5555',
        '-device', 'virtio-net-pci,netdev=network',
        '-serial', 'mon:stdio',
        '-vga', 'qxl',
        #'-display', 'gtk,gl=on',

        # Drives and disk images
        '-drive', 'index=0,if=virtio,id=system,file=system.sfs,format=raw,readonly',
        '-drive', 'index=1,if=virtio,id=ramdisk,file=ramdisk.img,format=raw,readonly',
        '-drive', 'if=none,id=usbstick,file=usb.qcow2,format=qcow2',

        # USB devices
        '-usb',
        '-device', 'usb-tablet,bus=usb-bus.0',
        '-device', 'nec-usb-xhci,id=xhci',  # Our emu USB stick is all 3.0 goodness
        '-device', 'usb-storage,id=usbdrive,bus=xhci.0,drive=usbstick',
    ]
}


def noop(a: T) -> T:
    return a


def env_bool(val: str) -> bool:
    return bool(int(val))


_environ_cfg: Dict[str, Tuple[str, Callable]] = {
    'job_workdir': ('JOB_WORKDIR', noop),
    'job_command': ('JOB_COMMAND', noop),
    'virtwifi_hack': ('VIRTWIFI_HACK', env_bool),
    'virtwificonnector_apk': ('VIRTWIFICONNECTOR_APK', noop),
    'permission_approve': ('PERMISSION_APPROVE', env_bool),
    'qemu_workdir': ('QEMU_WORKDIR', noop),
    'qemu_bin': ('QEMU_BIN', noop),
    'qemu_debug': ('QEMU_DEBUG', env_bool),
}


def get_config() -> dict:
    cfg = _default_cfg.copy()

    cfg_file = os.environ.get("ORCHESTRATOR_CONFIG", 'config.json')
    if not os.access(cfg_file, os.R_OK):
        if 'ORCHESTRATOR_CONFIG' in os.environ:
            warn(f"Config file '{cfg_file}' does not exist or is not readable", ResourceWarning)
    else:
        with open(cfg_file) as f:
            cfg.update(json.load(f))

    for item, (var, converter) in _environ_cfg.items():
        if var in os.environ:
            cfg[item] = converter(os.environ[var])

    return cfg
