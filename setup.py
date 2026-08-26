from setuptools import setup, find_packages

setup(
    name="nexus",
    version="0.8.0",
    packages=find_packages(),
    install_requires=["requests"],
    python_requires=">=3.10",
)
