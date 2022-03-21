# Schemata - Release 1.0.0 - Release Notes

This is the first release of Schemata as a standalone library.

Schemata was previously part of another repository that's used at Nagwa for the development of the XSDs used to define and validate internal XML formats. However, the code is sufficiently self-contained that it made sense to make it into its own library.

For this first release, that original Schemata code has been copied across, and tidied up. The original Schemata code was well-tested, as it was frequently in-use, so this first release of the Schemata code on its own is fairly robust - most of the changes made have been in the documentation.

## Summary of Changes and Additions

- The original Schemata code has been reorganised into relevant modules, and made into a Python package.
- A huge amount of inline documentation has been added to the library.
- A main README file has been added, which includes some description of the motivation for Schemata, as well as an introduction to the syntax, which should be useful for anyone who has not yet seen Schemata.

## Summary of Testing

- The original Schemata code had a small number of unit tests (86) in it, which covered the parser. No new unit tests have been added for this release; however, all 86 unit tests are passing.