"""
EpistemicFlow 安装脚本
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [
        line.strip() for line in fh if line.strip() and not line.startswith("#")
    ]

setup(
    name="epistemicflow",
    version="0.1.0",
    author="EpistemicFlow Team",
    author_email="team@epistemicflow.ai",
    description="AI驱动的自动化科研平台",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/epistemicflow",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.11",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.1.0",
            "black>=23.0.0",
            "mypy>=1.7.0",
            "ruff>=0.1.0",
            "pre-commit>=3.5.0",
        ],
        "openai": ["openai>=1.0.0"],
        "autogen": ["pyautogen>=0.2.0"],
        "postgres": ["asyncpg>=0.29.0"],
        "mysql": ["aiomysql>=0.2.0"],
    },
    entry_points={
        "console_scripts": [
            "epistemicflow=main:main",
        ],
    },
)
