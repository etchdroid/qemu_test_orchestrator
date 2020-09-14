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
    'permission_approve_buttons': ['DPAD_RIGHT', 'DPAD_RIGHT', 'ENTER'],
    'vnc_recorder': False,
    'vnc_recorder_debug': False,
    'vnc_recorder_bin': None,
    'vnc_recorder_output': 'qemu_recording.mp4',
    'vnc_recorder_port': 5910,
    'qemu_workdir': None,
    'qemu_bin': f'qemu-system-{os.uname().machine}',
    'qemu_debug': False,
    'qemu_force_kvm': False,
    'qemu_args': [
        # CPU
        '-smp', '2',

        # RAM
        '-m', '2048',

        # Linux
        '-kernel', 'kernel',
        '-append', 'root=/dev/ram0 androidboot.selinux=permissive androidboot.hardware=android_x86_64 console=ttyS0 '
                   'RAMDISK=vdb SETUPWIZARD=0',
        '-initrd', 'initrd.img',

        # Generic hardware
        '-audiodev', 'none,id=audionull', '-device', 'AC97,audiodev=audionull',
        '-netdev', 'user,id=network,hostfwd=tcp::5555-:5555',
        '-device', 'virtio-net-pci,netdev=network',
        '-chardev', 'socket,id=serial0,path=/tmp/qemu-android.sock,server',
        '-serial', 'chardev:serial0',
        '-vga', 'qxl',
        '-display', 'vnc=127.0.0.1:10',

        # Drives and disk images
        '-drive', 'index=0,if=virtio,id=system,file=system.sfs,format=raw,readonly',
        '-drive', 'index=1,if=virtio,id=ramdisk,file=ramdisk.img,format=raw,readonly',
        '-drive', 'if=none,id=usbstick,file=usb.img,format=raw',

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


def space_separated_values(val: str) -> list:
    return val.split(' ')


_environ_cfg: Dict[str, Tuple[str, Callable]] = {
    'job_workdir': ('JOB_WORKDIR', noop),
    'job_command': ('JOB_COMMAND', noop),
    'virtwifi_hack': ('VIRTWIFI_HACK', env_bool),
    'virtwificonnector_apk': ('VIRTWIFICONNECTOR_APK', noop),
    'permission_approve': ('PERMISSION_APPROVE', env_bool),
    'vnc_recorder': ('VNC_RECORDER', env_bool),
    'vnc_recorder_debug': ('VNC_RECORDER_DEBUG', env_bool),
    'vnc_recorder_bin': ('VNC_RECORDER_BIN', noop),
    'vnc_recorder_output': ('VNC_RECORDER_OUTPUT', noop),
    'vnc_recorder_port': ('VNC_RECORDER_PORT', int),
    'qemu_workdir': ('QEMU_WORKDIR', noop),
    'qemu_bin': ('QEMU_BIN', noop),
    'qemu_debug': ('QEMU_DEBUG', env_bool),
    'qemu_force_kvm': ('QEMU_FORCE_KVM', env_bool)
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
