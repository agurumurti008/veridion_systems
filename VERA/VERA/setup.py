#!/usr/bin/env python3
"""
VERA — Verification Engine for Runtime & Autonomous Checking
FILE: setup.py
DESC: Python package setup for VERA tools
"""
from setuptools import setup, find_packages

setup(
    name="vera-checker",
    version="1.0.0",
    description="VERA — Verification Engine for Runtime & Autonomous Checking",
    long_description=open("README.md").read(),
    author="Verification Team",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "numpy>=1.21",
        "scipy>=1.7",
        "pyyaml>=6.0",
        "pandas>=1.3",
        "matplotlib>=3.4",
    ],
    extras_require={
        "vcd":    ["vcdvcd>=1.0.5"],
        "spice":  ["ltspice>=0.0.9"],
        "matlab": [],  # Use MATLAB Engine API separately
        "all":    ["vcdvcd>=1.0.5", "ltspice>=0.0.9"],
    },
    entry_points={
        "console_scripts": [
            "vera-build=automation.builder.vera_builder:main",
            "vera-run=core.python.vera_postsim_engine:main",
            "vera-report=automation.reporter.vera_dashboard:main",
            "vera-waveload=automation.waveform_loader.vera_waveload:main",
            "vera-tbgen=automation.tb_gen.vera_tb_gen:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Scientific/Engineering :: Electronic Design Automation (EDA)",
        "Programming Language :: Python :: 3",
    ],
)
