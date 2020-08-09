from setuptools import setup, find_packages

setup(
    name='qemu_test_orchestrator',
    version='0.1',
    packages=find_packages(),
    license='GPL-3.0',
    author='Davide Depau',
    author_email='davide@depau.eu',
    install_requires=('paco',)
)
