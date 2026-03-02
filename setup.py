from setuptools import setup, find_packages

setup(
    name="rndsynth",
    version="1.0.0",
    packages=find_packages(exclude=["venv", "venv.*"]),
    url="",
    license="",
    author="Neil Baldwin",
    author_email="neilbaldwin@tutanota.com",
    description="AI-powered music generation and conversion for the Synthstrom Deluge",
    python_requires=">=3.8",
    install_requires=[
        "lxml>=4.2.4",
        "numpy>=1.20.0",
        "mido>=1.2.10",
        "soundfile>=0.12.0",
        "sounddevice>=0.4.6",
    ],
    extras_require={
        "full": [
            "demucs>=4.0.0",
            "basic-pitch>=0.3.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "deluge-ai=deluge_ai.cli:main",
        ],
    },
)
