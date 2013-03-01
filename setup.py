from setuptools import setup, find_packages

name = 'swiftmemcache'
requires=[]

setup(
    name=name,
    description='Swift Memcache',
    packages=find_packages(exclude=[]),
    install_requires=requires,
    entry_points={
        'console_scripts': [
        ],
        'paste.filter_factory': [
        'swift_middleware=swiftmemcache.middleware:filter_factory',
        ],
    },
)

