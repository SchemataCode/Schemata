import setuptools

with open("README.md", "r") as fo:
    long_description = fo.read()

setuptools.setup(
    name="schematacode",
    version="1.0.1",
    author="B. T. Milnes",
    description="Schemata is a file format that makes writing XML and JSON schemas easier.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/SchemataCode/Schemata",
    packages=["schemata"]
)
