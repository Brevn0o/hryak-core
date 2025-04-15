from setuptools import setup, find_packages

setup(
    name='hryak',
    version='0.1.0',
    packages=find_packages(),
    description='Logic package for Hryak',
    classifiers=[
        'Programming Language :: Python :: 3',
    ],
    install_requires=[
        'mysql-connector-python==9.1.0',
    ],
    python_requires='~=3.12.0',
)