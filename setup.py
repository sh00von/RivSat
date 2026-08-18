"""
RivSat: Satellite Remote Sensing of Water Turbidity & TSS.

A CoastSat-style, physics-based bio-optical processing framework for mapping
riverine, estuarine, and coastal water quality from Sentinel-2 MSI and
Landsat 8/9 OLI via Google Earth Engine.
"""

from setuptools import setup, find_packages
import os

version = "1.2.0"
try:
    with open(os.path.join("rivsat", "__init__.py"), "r") as f:
        for line in f:
            if line.startswith("__version__"):
                version = line.split("=")[1].strip().strip('"').strip("'")
                break
except FileNotFoundError:
    pass

long_description = ""
if os.path.exists("README.md"):
    with open("README.md", "r", encoding="utf-8") as f:
        long_description = f.read()

setup(
    name="rivsat",
    version=version,
    author="Md Minaruzzaman Shovon",
    description=(
        "CoastSat-style satellite remote sensing framework for mapping "
        "water turbidity (FNU) and Total Suspended Solids (TSS) in rivers and estuaries."
    ),
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/shovon/rivsat",
    license="MIT",
    packages=find_packages(exclude=["tests*", "outputs*"]),
    include_package_data=True,
    package_data={
        "rivsat.app.qt": [
            "assets/*.html",
            "assets/vendor/*.js",
            "assets/vendor/*.css",
            "assets/vendor/images/*.png",
        ],
    },
    python_requires=">=3.9",
    install_requires=[
        "earthengine-api>=0.1.350",
        "rasterio>=1.3.0",
        "numpy>=1.22.0",
        "scipy>=1.9.0",
        "pandas>=1.5.0",
        "geopandas>=0.12.0",
        "shapely>=2.0.0",
        "matplotlib>=3.6.0",
        "folium>=0.14.0",
        "tqdm>=4.64.0",
        "requests>=2.28.0",
    ],
    entry_points={
        "console_scripts": [
            "rivsat-gui=rivsat.app.qt.app:main",
        ],
    },
    extras_require={
        "full": [
            "cmocean>=3.0.0",
            "seaborn>=0.12.0",
            "ipywidgets>=8.0.0",
            "tifffile>=2023.1.0",
        ],
        "gui": [
            "PyQt6>=6.6.0",
            "PyQt6-WebEngine>=6.6.0",
            "matplotlib>=3.6.0",
            "folium>=0.14.0",
        ],
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: GIS",
        "Topic :: Scientific/Engineering :: Hydrology",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Operating System :: OS Independent",
    ],
    keywords=[
        "rivsat", "remote-sensing", "satellite", "turbidity", "TSS", "suspended-solids",
        "water-quality", "sentinel-2", "landsat", "google-earth-engine",
        "coastsat", "bio-optical", "nechad", "dogliotti", "river", "estuary",
    ],
)
