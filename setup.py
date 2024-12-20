# setup.py

from setuptools import setup, find_packages

setup(
    name="auto-mermaid-chart",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        'Pillow>=10.1.0',
        'dataclasses>=0.6',
        'typing-extensions>=4.8.0'
    ],
)