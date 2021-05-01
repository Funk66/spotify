from setuptools import setup

setup(
    name="spotify",
    version="0.1.0",
    author="Guillermo Guirao Aguilar",
    author_email="contact@guillermoguiraoaguilar.com",
    py_modules=["spotify"],
    description="Spotify API client",
    url="https://github.com/Funk66/spotify",
    license="MIT",
    classifiers=["Programming Language :: Python :: 3.9"],
    install_requires=['pyyaml', 'urllib3', 'certifi'],
    packages=["spotify"],
)
