# Schemata

Schemata is a file format that makes it easier to create schemas for XML and JSON files.

## Motivation

Schemata was created because many of the existing formats for XML schema are verbose. Among these is XSD. The XSD format, while flexible, requires a lot of mark-up (because it is an XML format) and is difficult to read. XSD files can easily become very large, and very disordered. This makes them difficult and tedious to maintain.

The Schemata format uses minimal, intuitive mark-up, making it easy to read and maintain. This is particularly useful when creating and maintaining schemas for multiple complex formats. 

While Schemata was originally designed for XML schemas, it became apparent that the same format could also be used to define JSON schemas. Support for this has been added.

## How does it work?

This code library does not actually _perform_ the validation of an XML or JSON file against the schema itself. Instead, this code library generates an XSD or JSON Schemas file that can be used for validation. The validation can then be _performed_ by any number of standard libraries. This has the advantage that the code library is easy to maintain, and its output is portable.

This code library can also generate documentation for an XML format based on the Schemata file. This documentation is not _quite_ perfect - there will always be nuances in how an XML format is used that cannot be accounted for in the schema - but generating the documentation from the Schemata file and then editing it can be **a lot** quicker than writing the whole thing manually.

## An Introduction to the Syntax

Let's start by considering a very simple XML file.

```xml
<?xml version="1.0" encoding="utf-8" ?>
<books>
    <book id="the_fellowship_of_the_ring">
        <title>The Fellowship of the Ring</title>
        <subtitle>The Lord of the Rings, Book 1</subtitle>
        <isbn>0261103571</isbn>
    </book>
    <book id="pride_and_prejudice">
        <title>Pride and Prejudice</title>
        <subtitle></subtitle>
        <isbn>9780141040349</isbn>
    </book>
    <book id="a_game_of_thrones">
        <title>A Game of Thrones</title>
        <subtitle>A Song of Ice and Fire, Book 1</subtitle>
        <isbn>9780006479888</isbn>
    </book>
</books>
```

This XML file contains a list of books, with some basic information about each book. We can call this XML format Book List XML.

In writing a schema for Book List XML, we might start by defining the root element `<books>`, which we can do in Schemata as below.

```
root element books {
}
```

This code block tells us that in Book List XML there can be an element `<books>`, and that this element can be a root element of the document. We haven't said anything about the contents of this element yet, because we haven't defined any other elements in our Schemata file.

Note that the string that appears after `root element` in the code block above defines both the _reference_ to this structure in the Schemata file (the name by which this element is referred to in the rest of the Schemata file), and the _tag name_ of the XML element. These two things can be set differently, as shown below.

```
root element my_root_element {
    tagName: 'books';
}
```

This code block still tells us that in Book List XML there can be a root element `<books>`, but if we need to refer to it elsewhere in the Schemata file, it will be referred to as `my_root_element`. (Most of the time you won't want to have the reference and the tag name be different - it's only when schemas get much more complicated that you might need to.)

We now want to define an element `<book>` that has an `id` attribute. We need to first define the `id` attribute, which we can do in Schemata as below.

```
attribute id {
    valueType: string;
}
```

This code block tells us that in Book List XML there can be an attribute `id`, the value of which can be any string. We can now define the `<book>` element.

```
element book {
    attributes: id;
}
```

This code block tells us that in Book List XML there can be an element `<book>`, which has an attribute `id`.

Now we want to say that this `<book>` element can be a subelement of the `<books>` element. In order to do this, we need to adjust the first code block we wrote, as below.

```
root element books {
    allowedContent: [ book (n >= 0) ];
}
```

This code block now tells us that the `<books>` element can have `<book>` subelements. The expression `n >= 0` indicates that there can be any number of `<book>` subelements, including zero. (That wouldn't be a very useful file, but we'll allow it.) The square brackets in the `allowedContent` property indicate that the subelements must appear in the order defined. This doesn't really matter in this case, as only one type of subelement - the `<book>` subelement - can exist. This becomes more useful when an element can have many different types of subelement (as we shall see later).

So far we have

```
root element books {
    allowedContent: [ book (n >= 0) ];
}

attribute id {
    valueType: string;
}

element book {
    attributes: id;
}
```

At this point it's worth mentioning that we can be more specific with what values things like attributes can have. In Schemata, it's possible to define new data types. This can be very useful, as often you will want to use the same data type in many places in your schema, but you will want to define it in one place and reuse it everywhere.

In our example XML file above, we can see that the ids of the books always consist of letters, numbers, and underscores - never spaces, hyphens, apostrophes, et cetera. We can define a new data type in Schemata as below.

```
dataType _id {
    baseType: string;
    allowedPattern: '[A-Za-z0-9_]+';
}
```

This code block defines a new data type `_id`. (By convention, it's a good idea to start data type references with an underscore, to prevent clashes with attribute structures.) In this case we have stated that the base type of this new data type is a string, and then we've stated that this string must conform to the given regular expression. Putting this all together, we get

```
root element books {
    allowedContent: [ book (n >= 0) ];
}

dataType _id {
    baseType: string;
    allowedPattern: '[A-Za-z0-9_]+';
}

attribute id {
    valueType: _id;
}

element book {
    attributes: id;
}
```

We now want to define the possible subelements of the `<book>` element. Let's start with the `<title>` element.

```
element title {
    allowedContent: *any text*;
}
```

In this case, we want to allow the element to contain any text, but no subelements. We do this with `*any text*`.

The `<subtitle>` and `<isbn>` elements we can define to work in the same way.

```
element subtitle {
    allowedContent: *any text*;
}

element isbn {
    allowedContent: *any text*;
}
```

Finally, we need to 'attach' these subelements to the `<book>` element - i.e., we need to state that they are possible subelements. We can do this by editing the definition of the `<book>` structure.

```
element book {
    attributes: id;
    allowedContent: [ title, subtitle (optional), isbn ];
}
``` 

Here we have specified that the `<title>` element can be a subelement of `<book>`. As we have not put an n-expression in brackets after it, there must be exactly 1 `<title>` element. The `<subtitle>` element we have indicated is optional, meaning that there can be 0 or 1 `<subtitle>` elements, but no more. We have specified that there must be exactly 1 `<isbn>` element. 

The use of square brackets here indicates that these elements must appear in this order. So the XML below would be wrong, and would fail validation against the XSD.

```xml
<book id="the_fellowship_of_the_ring">
    <isbn>0261103571</isbn>
    <title>The Fellowship of the Ring</title>
    <subtitle>The Lord of the Rings, Book 1</subtitle>
</book>
```

If we wanted to specify that the order of the subelements does not matter, we would use recurve brackets, as below.

```
element book {
    attributes: id;
    allowedContent: { title, subtitle (optional), isbn };
}
``` 

Putting everything together, we get

```
root element books {
    allowedContent: [ book (n >= 0) ];
}

dataType _id {
    baseType: string;
    allowedPattern: '[A-Za-z0-9_]+';
}

attribute id {
    valueType: _id;
}

element book {
    attributes: id;
    allowedContent: [ title, subtitle (optional), isbn ];
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

This schema, when put through the Schemata code, would produce an XSD file that describes the XML file we started with.





A Schemata file defines a number of **structures**. These structures are used to describe different things within an XML file - elements, attributes, data - or a JSON file - objects, properties, arrays, data. Structures can in turn refer to other structures that they contain.


## Credits

Made by B. T. Milnes for Nagwa Limited
