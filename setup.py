from setuptools import setup, find_packages

setup(
    name='hryak',
    version='0.1.0',
    packages=find_packages(),
    description='Logic package for Hryak',
    classifiers=[
        'Programming Language :: Python :: 3',
    ],
    include_package_data=True,
    install_requires=[
        'mysql-connector-python==9.2.0',
        'cachetools == 5.5.0',
        'aiocache == 0.12.3',
        'aiofiles == 24.1.0',
        'requests == 2.32.3',
        'numpy == 2.2.1',
        'scipy == 1.14.1',
    ],
    python_requires='~=3.12.0',
)