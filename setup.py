"""
Setup configuration for support-triage-agent PyPI package
"""
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="support-triage-agent",
    version="1.0.0",
    author="Anmoll",
    author_email="anmoll@example.com",
    description="🎯 Multi-domain AI support triage agent with 18 intelligence features",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/AnmollCodes/support-triage-agent",
    packages=find_packages(where="code"),
    package_dir={"": "code"},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Customer Service",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Office/Business :: News/Diary",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.10",
    install_requires=[
        "anthropic>=0.40.0,<1.0.0",
        "httpx>=0.27.0,<1.0.0",
        "beautifulsoup4>=4.12.0,<5.0.0",
        "lxml>=5.0.0,<6.0.0",
        "rank-bm25>=0.2.2,<1.0.0",
        "pydantic>=2.5.0,<3.0.0",
        "rich>=13.7.0,<14.0.0",
        "python-dotenv>=1.0.0,<2.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.0.0",
        ],
        "api": [
            "fastapi>=0.100.0",
            "uvicorn>=0.23.0",
        ],
        "cli": [
            "click>=8.1.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "support-triage=agent:cli_main",
        ],
    },
    keywords=[
        "support",
        "triage",
        "ai",
        "classification",
        "chatbot",
        "customer-service",
        "nlp",
        "machine-learning",
    ],
    project_urls={
        "Bug Reports": "https://github.com/AnmollCodes/support-triage-agent/issues",
        "Documentation": "https://github.com/AnmollCodes/support-triage-agent#readme",
        "Source Code": "https://github.com/AnmollCodes/support-triage-agent",
    },
)
