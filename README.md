# Schemata

Schemata is a file format that makes it easier to create schemas for XML and JSON files.

## Motivation

Schemata was created because many of the existing formats for XML schema are verbose. Among these is XSD. The XSD format, while flexible, requires a lot of mark-up (because it is an XML format) and is difficult to read. XSD files can easily become very large, and very disordered. This makes them difficult and tedious to maintain.

The Schemata format uses minimal, intuitive mark-up, making it easy to read and maintain. This is particularly useful when creating and maintaining schemas for multiple complex formats. 

While Schemata was originally designed for XML schemas, it became apparent that the same format could also be used to define JSON schemas. Support for this has been added.

## How does it work?

This code library does not actually _perform_ the validation of an XML or JSON file against the schema itself. Instead, this code library generates an XSD or JSON Schemas file that can be used for validation. The validation can then be _performed_ by any number of standard libraries. This has the advantage that the code library is easy to maintain, and its output is portable.

## Principles of Design

A Schemata file defines a number of **structures**. These structures are used to describe different things within an XML file - elements, attributes, data - or a JSON file - objects, properties, arrays, data. Structures can in turn refer to other structures that they contain.

Below is shown an example Schemata file for an XML file that contains a list of books.

```

root element books {
    allowedContent: [ book (n >= 0) ];
}

element book {
    attributes: id;
    allowedContent: title, subtitle (optional), isbn;
}

attribute id {
    valueType: _id;
}

dataType _id {
    baseType: string;
    allowedPattern: '[A-Za-z0-9\-_]+';
}

element title {
    allowedContent: *any text*;
}

element subtitle {
    allowedContent: *any text*;
}

element isbn {
    allowedContent: *any text*;
}

```

This schema file first says that there is a possible root XML element <books>.
