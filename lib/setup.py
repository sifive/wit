import setuptools

version = {}
with open("wit/version.py") as fd:
    exec(fd.read(), version)

setuptools.setup(
    name='wit-sifive',
    version=version['__version__'],
    description="Wit: Workspace Integration Tool",
    long_description="See README.md at https://github.com/sifive/wit/",
    author='SiFive',
    author_email='',
    url='www.github.com/sifive/wit',
    packages=["wit"],
    entry_points={'console_scripts': ['wit=wit.main:main']},
    python_requires='>=3.5',
    classifiers=["License :: OSI Approved :: Apache Software License"],
)
