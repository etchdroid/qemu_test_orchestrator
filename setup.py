from setuptools import setup

setup(
    name='qemu_test_orchestrator',
    version='0.1',
    packages=['qemu_android_test_orchestrator'],
    license='GPL-3.0',
    author='Davide Depau',
    author_email='davide@depau.eu',
    install_requires=('paco',)
)
