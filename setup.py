from setuptools import setup, find_packages
from setuptools.command.install import install
from setuptools.command.develop import develop
import subprocess
import sys

def parse_requirements(filename):
    """Reads a requirements.txt file and returns a list of dependencies."""
    with open(filename, 'r') as f:
        return [line.strip() for line in f.readlines() if line.strip() and not line.startswith('#')]

# Custom install command that runs pre-commit install after setup
# This will execute when the package is installed with: pip install .
class PostInstallCommand(install):
    def run(self):
        install.run(self)
        try:
            subprocess.check_call(['pre-commit', 'install'])
            print("Installed pre-commit hooks")
        except subprocess.CalledProcessError as e:
            print(f"Error installing pre-commit hooks: {e}")
        except FileNotFoundError:
            print("pre-commit not found. Please install it with 'pip install pre-commit'")

# Custom develop command for development mode
# This will execute when the package is installed with: pip install -e .
class PostDevelopCommand(develop):
    def run(self):
        develop.run(self)
        try:
            subprocess.check_call(['pre-commit', 'install'])
            print("Installed pre-commit hooks")
        except subprocess.CalledProcessError as e:
            print(f"Error installing pre-commit hooks: {e}")
        except FileNotFoundError:
            print("pre-commit not found. Please install it with 'pip install pre-commit'")

# Read production dependencies from requirements.txt
install_requires = parse_requirements('requirements.txt')

setup(
    name="Callsight_API",  # Your package name
    version="1.0.0",  # Version
    packages=find_packages(),
    install_requires=install_requires,  # Production dependencies from requirements.txt
    extras_require={
        'dev': [
            'pytest',
            'pytest-asyncio',
            'pytest-mock',
            'pytest-cov',
            'pre-commit'
        ]
    },
    cmdclass={
        'install': PostInstallCommand,
        'develop': PostDevelopCommand,
    },
    entry_points={
        'console_scripts': [
            'callsight-api = app.cli:main',
        ],
    }
)
