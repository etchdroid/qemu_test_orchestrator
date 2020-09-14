import asyncio
from threading import Lock
from typing import Iterable, Dict, Any, Optional


# The synchronized access was implemented because I had initially planned to use threads for some operations.
# The async API turned out to be perfectly fine. I'm going to leave this here for future use if threads are required, it
# shouldn't cause any performance penalties in single threaded asynchronous usage anyway.


class SynchronizedObject:
    __lock = Lock()
    __vars: Dict[str, Any] = {}

    # Unused vars, for type hinting
    config: Optional[Dict[str, Any]] = None
    qemu_proc: Optional[asyncio.subprocess.Process] = None
    job_proc: Optional[asyncio.subprocess.Process] = None
    adb_proc: Optional[asyncio.subprocess.Process] = None
    vnc_recorder_proc: Optional[asyncio.subprocess.Process] = None
    qemu_sock_reader: Optional[asyncio.StreamReader] = None
    qemu_sock_writer: Optional[asyncio.StreamWriter] = None
    qemu_sock_stopdebug: Optional[bool] = None
    qemu_sock_buffer: Optional[bytes] = None

    vm_timeout_multiplier = 1

    def __getattribute__(self, item: str) -> Any:
        if not item.startswith('_'):
            with self.__lock:
                if item in self.__vars:
                    return self.__vars[item]
        return super().__getattribute__(item)

    def __setattr__(self, key: str, value: Any) -> None:
        if key.startswith("_"):
            return super(SynchronizedObject, self).__setattr__(key, value)
        with self.__lock:
            self.__vars[key] = value

    def __dir__(self) -> Iterable[str]:
        supdir = set(super().__dir__())
        with self.__lock:
            supdir.update(set(self.__vars.keys()))
        return tuple(supdir)
