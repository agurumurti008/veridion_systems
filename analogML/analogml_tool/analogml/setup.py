from setuptools import setup, find_packages

setup(
    name="analogml",
    version="0.1.0",
    description="Physics-Backed Multi-Fidelity Neural Models for Analog IC Design",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "torch>=2.0.0",
        "numpy>=1.24.0",
        "scipy>=1.10.0",
        "pandas>=2.0.0",
        "scikit-learn>=1.2.0",
        "networkx>=3.1",
        "matplotlib>=3.7.0",
        "streamlit>=1.28.0",
        "plotly>=5.15.0",
        "gpytorch>=1.10.0",
        "torchdiffeq>=0.2.3",
        "sympy>=1.12",
        "joblib>=1.3.0",
        "tqdm>=4.65.0",
    ],
    extras_require={
        "symbolic": ["pysr>=0.17.0"],
        "gnn": ["torch-geometric>=2.3.0"],
    },
    entry_points={
        "console_scripts": [
            "analogml-dashboard=analogml.ui.dashboard:main",
        ]
    },
)
