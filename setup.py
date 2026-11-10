from setuptools import setup, find_packages

setup(
    name="llm-code-eval-kit",
    version="0.1.0",
    packages=find_packages(where="."),
    python_requires=">=3.10",
    install_requires=["numpy>=1.26", "pyyaml>=6.0"],
    entry_points={"console_scripts": ["eval-llm=cli:main"]},
)
