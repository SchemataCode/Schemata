import os 
import logging 
import re
from lxml.etree import ElementTree as XMLElementTree, Element as XMLElement, SubElement as XMLSubelement, Comment as XMLComment, QName, indent 
import json 
from schemata.structures import * 

logger = logging.getLogger("schemata.exporters")


class JSONSchemasExporter(object):
    """
    This class takes a Schemata schema and exports it into the JSON Schemas format.

    To do:

    This class does not implement *every* feature of JSON Schemas yet, as it has been developed for a very specific use-case.

    ...

    Attributes
    ----------
    _js : string
        The JSON Schemas specification being used. This is the value of the $schema property. Do not change. 
    """
    def __init__(self):
        self._js = "https://json-schema.org/draft/2020-12/schema"

    def exportSchema(self, schema, versionNumber, schemaURI, filePath = ""):
        """
        Constructs the root JSON object for a JSON Schemas export of the given schema, and saves it to the given file path.

        Parameters
        ----------
        schema : Schema
            The schema to export.
        versionNumber : string
            The version number of this schema. Can follow any convention you like.
        schemaURI : string
            A URI to this schema.
        filePath : string
            The path to which to save the output. Use an empty string to indicate that the output should not be saved as a file.

        Returns
        -------
        The JSON object.
        """

        logging.debug("Exporting schema for {} as JSON Schema.".format(schema.formatName))

        o1 = {}
        o1["$schema"] = self._js 
        o1["$id"] = schemaURI 
        o1["title"] = "{} ({})".format(schema.formatName, versionNumber)
        o1["type"] = "object"

        rootObject = schema.getRootObjectStructures()[0]

        self._exportObject(schema, rootObject, o1)

        if filePath != "":
            with open(filePath, "w") as fo:
                json.dump(o1, fo, indent=4)

        return o1 

    def _exportArray(self, schema, _array, jsonObject):
        """
        Internal function. Exports an array structure to the JSON Schemas format.

        Parameters
        ----------
        schema : Schema
            The schema being exported.
        _array : ArrayStructure
            The array structure being exported.
        jsonObject : dictionary
            The dictionary / JSON object to which to attach this array.

        Returns
        -------
        None
        """

        logger.debug("Exporting array structure {}.".format(_array.reference))

        jsonObject["type"] = "array"

        if _array.itemTypeReference == "string":
            jsonObject["items"] = {"type": "string"}
        elif _array.itemTypeReference == "integer":
            jsonObject["items"] = {"type": "integer"}
        elif _array.itemTypeReference == "decimal":
            jsonObject["items"] = {"type": "decimal"}
        elif _array.itemTypeReference == "boolean":
            jsonObject["items"] = {"type": "boolean"}
        elif isinstance(_array.itemType, DataStructure):
            ds = _array.itemType

            if ds.baseStructureReference == "string":
                jsonObject["items"] = {}
                jsonObject["items"]["type"] = "string"

                if ds.allowedPattern != "":
                    jsonObject["items"]["pattern"] = ds.allowedPattern

                if ds.allowedValues != []:
                    jsonObject["items"]["enum"] = ds.allowedValues

    def _exportObject(self, schema, _object, jsonObject):
        """
        Internal function. Exports an object structure to the JSON Schemas format.

        Parameters
        ----------
        schema : Schema
            The schema being exported.
        _object : ObjectStructure
            The object structure being exported.
        jsonObject : dictionary
            The dictionary / JSON object to which to attach this array.

        Returns
        -------
        None
        """

        logger.debug("Exporting object structure {}.".format(_object.reference))

        jsonObject["type"] = "object"
        jsonObject["properties"] = {}
        jsonObject["required"] = []
        jsonObject["additionalProperties"] = False

        for _property in _object.properties:
            p = _property.propertyStructure
            pn = p.propertyName
            jsonObject["properties"][pn] = {}
            jsonObject["properties"][pn]["description"] = p.metadata.description

            self._exportProperty(schema, p, jsonObject["properties"][pn])

            if _property.isOptional == False:
                jsonObject["required"].append(pn)

    def _exportProperty(self, schema, _property, jsonObject):
        """
        Internal function. Exports a property structure to the JSON Schemas format.

        Parameters
        ----------
        schema : Schema
            The schema being exported.
        _property : PropertyStructure
            The property structure being exported.
        jsonObject : dictionary
            The dictionary / JSON object to which to attach this array.

        Returns
        -------
        None
        """

        logger.debug("Exporting property structure {}.".format(_property.reference))

        if _property.valueTypeReference == "string":
            jsonObject["type"] = "string"
        elif _property.valueTypeReference == "integer":
            jsonObject["type"] = "integer"
        elif _property.valueTypeReference == "decimal":
            jsonObject["type"] = "number"
        elif _property.valueTypeReference == "boolean":
            jsonObject["type"] = "boolean"
        elif isinstance(_property.valueType, DataStructure):
            ds = _property.valueType

            if ds.baseStructureReference == "string":
                jsonObject["type"] = "string"

                if ds.allowedPattern != "":
                    jsonObject["pattern"] = ds.allowedPattern

                if ds.allowedValues != []:
                    jsonObject["enum"] = ds.allowedValues
        elif isinstance(_property.valueType, ArrayStructure):
            _as = _property.valueType

            self._exportArray(schema, _as, jsonObject)
        elif isinstance(_property.valueType, ObjectStructure):
            _os = _property.valueType

            self._exportObject(schema, _os, jsonObject)


class XSDExporter(object):
    """
    A class that takes a Schemata schema and exports it to the XSD format.

    ...

    Attributes
    ----------
    _xs : string
        The value of xmlns:xs. Do not change.
    _typePrefix : string
        XSD allows the definition of reusable types. This exporter takes full advantage of that, as it's an approach that
        closely matches how Schemata works, making the export easier. This string is a prefix that's applied to type names
        in the XSD, to distinguish them easily from other kinds of elements. You can change this if you want, but there's
        not much point. Set to '__type__' by default.
    """

    def __init__(self):
        self._xs = "http://www.w3.org/2001/XMLSchema"
        self._typePrefix = "__type__"

    def _getXSDTypeName(self, structure):
        if isinstance(structure, DataStructure):
            return self._typePrefix + "d__" + structure.reference 
        if isinstance(structure, ElementStructure):
            return self._typePrefix + "e__" + structure.reference 
        if isinstance(structure, AttributeStructure):
            return self._typePrefix + "a__" + structure.reference 

        raise Exception("Cannot create XSD type name for {}.".format(structure.reference))

    def exportSchema(self, schema, versionNumber, filePath = ""):
        """
        Exports a schema as XSD, saving it to the given file path.

        Parameters
        ----------
        schema : Schema
            The schema to export.
        versionNumber : string
            The version number of the schema.
        filePath : string
            The path to which to save the XSD file. Use an empty string to indicate that the XSD object should not be saved to a file.

        Returns
        -------
        An ElementTree which is the XSD schema.
        """

        xs = self._xs

        logging.debug("Exporting schema for {} as XSD.".format(schema.formatName))

        e1 = XMLElement(QName(xs, "schema"))
        e1.set("elementFormDefault", "qualified")

        # Put a comment at the top of the XSD file saying what XML format it's for.
        if schema.formatName != "":
            c1 = XMLComment(" An XSD file for {} ({}). ".format(schema.formatName, versionNumber))

            e1.append(c1)

        # First export all of the data structures, as these are more basic, and then export all of the element structures.
        self._exportDataStructures(schema, e1)
        self._exportElementStructures(schema, e1)

        logging.debug("Exporting root elements.")

        # The root element structures are exported last. This means that the output XSD file should be 'read' in reverse.
        roots = schema.getRootElementStructures()

        for root in roots:
            logging.debug("Exporting element <{}>.".format(root.elementName))

            e2 = XMLElement(QName(xs, "element"))
            e2.set("name", root.elementName)
            e2.set("type", self._getXSDTypeName(root))

            e1.append(e2)

        tree = XMLElementTree(e1)
        indent(tree, space="    ")

        if filePath != "":
            tree.write(filePath, xml_declaration=True, encoding="utf-8", pretty_print=True)

        return tree 

    def _exportDataStructures(self, schema, xsdElement):
        """
        Exports all of the data structures in the schema.

        Parameters
        ----------
        schema : Schema
            The schema being exported.
        xsdElement : Element
            The XML element to which to attach these data structures.

        Returns
        -------
        None 
        """

        xs = self._xs 

        logging.debug("Exporting data structures.")

        dataStructures = schema.getDataStructures()

        for dataStructure in dataStructures:
            # If a data structure isn't actually used in the schema, don't export it.
            if not dataStructure.isUsed:
                continue 

            logging.debug("Exporting data structure '{}'.".format(dataStructure.reference))

            e1 = XMLElement(QName(xs, "simpleType"))
            e1.set("name", self._getXSDTypeName(dataStructure))

            if dataStructure.baseStructureReference == "string":
                logging.debug(f"'{dataStructure.reference}' has an XSD base of string.")

                e2 = XMLElement(QName(xs, "restriction"))
                e2.set("base", "xs:string")

                if dataStructure.allowedPattern != "":
                    logging.debug(f"Setting pattern value to '{dataStructure.allowedPattern}'")

                    e3 = XMLElement(QName(xs, "pattern"))
                    e3.set("value", dataStructure.allowedPattern)

                    e2.append(e3)

                elif dataStructure.allowedValues:
                    logging.debug(f"Setting enumeration values.")

                    for value in dataStructure.allowedValues:
                        e3 = XMLElement(QName(xs, "enumeration"))
                        e3.set("value", value)

                        e2.append(e3)

                e1.append(e2)

            elif dataStructure.baseStructureReference == "decimal":
                logging.debug(f"'{dataStructure.reference}' has an XSD base of decimal.")

                e2 = XMLElement(QName(xs, "restriction"))
                e2.set("base", "xs:decimal")

                e1.append(e2)

            elif dataStructure.baseStructureReference == "integer":
                logging.debug(f"'{dataStructure.reference}' has an XSD base of integer.")

                e2 = XMLElement(QName(xs, "restriction"))
                e2.set("base", "xs:integer")

                if dataStructure.minimumValue != None:
                    logging.debug(f"Setting minInclusive value.")

                    e3 = XMLElement(QName(xs, "minInclusive"))
                    e3.set("value", str(dataStructure.minimumValue))

                    e2.append(e3)

                if dataStructure.maximumValue != None:
                    logging.debug(f"Setting maxInclusive value.")

                    e3 = XMLElement(QName(xs, "maxInclusive"))
                    e3.set("value", str(dataStructure.maximumValue))

                    e2.append(e3)

                e1.append(e2)

            elif dataStructure.baseStructureReference == "boolean":
                logging.debug(f"'{dataStructure.reference}' has an XSD base of boolean.")

                e2 = XMLElement(QName(xs, "restriction"))
                e2.set("base", "xs:boolean")

                e1.append(e2)

            xsdElement.append(e1)

            logging.debug("Exported data structure '{}'.".format(dataStructure.reference))

        logging.debug("Exported data structures.")
    
    def _exportElementStructures(self, schema, xsdElement):
        """
        Exports all of the element structures in the schema.

        Parameters
        ----------
        schema : Schema
            The schema being exported.
        xsdElement : Element
            The XML element to which to attach these element structures.

        Returns
        -------
        None 
        """

        xs = self._xs 

        logging.debug("Exporting element structures.")

        elementStructures = schema.getElementStructures()

        for elementStructure in elementStructures:
            # If the element structure isn't actually used in the schema (i.e., it isn't defined as a possible root element or subelement of another element), don't export it.
            if not elementStructure.isUsed:
                continue 

            logging.debug("Exporting element structure '{}' <{}>.".format(elementStructure.reference, elementStructure.elementName))

            # Here we decide whether the element is a 'simpleType' element or a 'complexType' element - it's quite an unintuitive distinction.
            if not elementStructure.hasContent:

                e1 = XMLElement(QName(xs, "complexType"))
                e1.set("name", self._getXSDTypeName(elementStructure))

                self._exportAttributes(schema, elementStructure.attributes, e1)

                xsdElement.append(e1)

            elif elementStructure.contentIsElementsOnly:

                e1 = XMLElement(QName(xs, "complexType"))
                e1.set("name", self._getXSDTypeName(elementStructure))
                e1.set("mixed", "false")

                self._exportSubelements(schema, elementStructure.allowedContent, e1)
                self._exportAttributes(schema, elementStructure.attributes, e1)

                xsdElement.append(e1)

            elif elementStructure.contentIsElementsAndAnyText:

                e1 = XMLElement(QName(xs, "complexType"))
                e1.set("name", self._getXSDTypeName(elementStructure))
                e1.set("mixed", "true")

                self._exportSubelements(schema, elementStructure.allowedContent, e1)
                self._exportAttributes(schema, elementStructure.attributes, e1)

                xsdElement.append(e1)

            elif elementStructure.contentIsAnyText and elementStructure.hasAttributes:

                e1 = XMLElement(QName(xs, "complexType"))
                e1.set("name", self._getXSDTypeName(elementStructure))

                e2 = XMLElement(QName(xs, "simpleContent"))

                e3 = XMLElement(QName(xs, "extension"))            
                e3.set("base", "xs:string")

                self._exportAttributes(schema, elementStructure.attributes, e3)

                e2.append(e3)
                e1.append(e2)
                xsdElement.append(e1)

            elif elementStructure.contentIsAnyText and not elementStructure.hasAttributes:

                e1 = XMLElement(QName(xs, "simpleType"))
                e1.set("name", self._getXSDTypeName(elementStructure))

                e2 = XMLElement(QName(xs, "restriction"))            
                e2.set("base", "xs:string")

                e1.append(e2)
                xsdElement.append(e1)

            elif elementStructure.contentIsSingleValue and elementStructure.hasAttributes:

                e1 = XMLElement(QName(xs, "complexType"))
                e1.set("name", self._getXSDTypeName(elementStructure))

                e2 = XMLElement(QName(xs, "simpleContent"))

                e3 = XMLElement(QName(xs, "extension")) 

                if elementStructure.valueTypeReference == "decimal":
                    e3.set("base", "xs:decimal")
                elif elementStructure.valueTypeReference == "integer":
                    e3.set("base", "xs:integer")
                elif elementStructure.valueTypeReference == "boolean":
                    e3.set("base", "xs:boolean")
                else:
                    e3.set("base", self._getXSDTypeName(elementStructure.valueType))

                self._exportAttributes(schema, elementStructure.attributes, e3)

                e2.append(e3)
                e1.append(e2)
                xsdElement.append(e1)

            elif elementStructure.contentIsSingleValue and not elementStructure.hasAttributes:

                e1 = XMLElement(QName(xs, "simpleType"))
                e1.set("name", self._getXSDTypeName(elementStructure))

                e2 = XMLElement(QName(xs, "restriction"))    

                if elementStructure.valueTypeReference == "decimal":
                    e2.set("base", "xs:decimal")
                if elementStructure.valueTypeReference == "integer":
                    e2.set("base", "xs:integer")
                elif elementStructure.valueTypeReference == "boolean":
                    e2.set("base", "xs:boolean")
                else:
                    e2.set("base", self._getXSDTypeName(elementStructure.valueType))

                e1.append(e2)
                xsdElement.append(e1)

            else:
                logging.warn("Could not export element structure '{}' <{}>.".format(elementStructure.reference, elementStructure.elementName))

    def _exportSubelements(self, schema, elements, xsdElement):
        """
        Exports a structure list to XSD.

        Parameters
        ----------
        schema : Schema
            The schema being exported.
        elements : StructureList
            The structure list being exported (representing the subelements of an element).
        xsdElement : Element
            The XML element to which to attach this list.

        Returns
        -------
        None 
        """

        xs = self._xs 

        xsdIndicatorType = "sequence"

        # Schemata uses a bit more natural language when it comes to lists of elements than XSD does.
        # Here we have to translate from the language of Schemata to the language of XSD.
        # OrderedStructureList correlates clearly to an XSD sequence.
        # StructureChoice correlates clearly to an XSD choice.
        # UnorderedStructureList can be represented by an XSD choice that can be used any number of times. (This is not perfect.)
        # This here is one of the reasons why Schemata is nicer to use than XSD - this is a pain to do by hand in XSD.
        if isinstance(elements, OrderedStructureList):
            e1 = XMLElement(QName(xs, "sequence"))
        if isinstance(elements, UnorderedStructureList):
            xsdIndicatorType = "choice"

            e1 = XMLElement(QName(xs, "choice"))
            e1.set("minOccurs", "0")
            e1.set("maxOccurs", "unbounded")
        if isinstance(elements, StructureChoice):
            xsdIndicatorType = "choice"

            e1 = XMLElement(QName(xs, "choice"))
        if elements == None:
            return 

        for element in elements.structures:
            if isinstance(element, OrderedStructureList) or isinstance(element, UnorderedStructureList) or isinstance(element, StructureChoice):
                self._exportSubelements(schema, element, e1)
            else:
                if isinstance(element, AnyTextUsageReference):
                    continue 

                logging.debug(f"Exporting element of type {type(element)}.")
                logging.debug(f"Exporting {self._getXSDTypeName(element.elementStructure)}.")

                e3 = XMLElement(QName(xs, "element"))
                e3.set("name", element.elementStructure.elementName)
                e3.set("type", self._getXSDTypeName(element.elementStructure))
                p = element.minimumNumberOfOccurrences
                q = element.maximumNumberOfOccurrences 

                if xsdIndicatorType == "sequence":
                    if p != 1:
                        e3.set("minOccurs", str(p))

                    if q != 1:
                        e3.set("maxOccurs", "unbounded" if q == -1 else str(q))

                e1.append(e3)

        xsdElement.append(e1)

    def _exportAttributes(self, schema, attributes, xsdElement):
        """
        Exports the given attribute structures to XSD.

        Parameters
        ----------
        schema : Schema
            The schema being exported.
        attributes : list of AttributeStructure
            The attribute structures being exported.
        xsdElement : Element
            The XML element to which to attach these attribute structures.

        Returns
        -------
        None 
        """

        xs = self._xs 
        baseTypes = ["string", "integer", "boolean"]

        for attribute in attributes:
            a = attribute.attributeStructure 

            e1 = XMLElement(QName(xs, "attribute"))
            e1.set("name", a.attributeName)

            if a.dataStructureReference in baseTypes:
                if a.dataStructureReference == "string":
                    e1.set("type", "xs:string")
                if a.dataStructureReference == "integer":
                    e1.set("type", "xs:integer")
                if a.dataStructureReference == "boolean":
                    e1.set("type", "xs:boolean")
            else:
                e1.set("type", self._getXSDTypeName(a.dataStructure))

            e1.set("use", "optional" if attribute.isOptional else "required")

            xsdElement.append(e1)


class SpecificationGenerator(object):
    """
    A class for generating specifications / human-readable documentation from Schemata schemas. The generated documents are in Markdown. The generation is not perfect, but it 
    makes the process of writing a specification / human-readable documentation a lot quicker.

    To do:

    This only works for XML schemas at the moment - need to extend it to JSON schemas.
    Would be nice to be able to generate documentation in HTML as well as Markdown.
    """

    def __init__(self):
        pass 

    def generateSpecification(self, schema, filePath):
        with open(filePath, "w") as fileObject:

            rootElements = schema.getPossibleRootElementStructures()
            nonRootElements = schema.getNonRootElementStructures()
            elements = rootElements + nonRootElements 

            fileObject.write("# {} Specification\n\n".format(schema.formatName))
            fileObject.write("This document gives the specification for {}.\n\n".format(schema.formatName))

            fileObject.write("## Table of Contents\n\n")

            for element in elements:
                fileObject.write("- [The &lt;{}&gt; element](#the-{}-element)\n".format(element.elementName, re.sub("_", "-", element.elementName)))

            for element in elements:
                fileObject.write("\n\n<br /><br />\n\n")
                fileObject.write("## The &lt;{}&gt; element\n\n".format(element.elementName))
                fileObject.write("{}\n\n".format(element.description.replace("<", "&lt;").replace(">", "&gt;")))
                fileObject.write("### Attributes\n\n")

                aa = []

                if element.attributes:
                    fileObject.write("| Name | Required | Allowed Values | Description |\n")
                    fileObject.write("|---|---|---|---|\n")

                    for attribute in element.attributes:
                        a = schema.getAttributeStructureByReference(attribute.attributeReference)
                        d = schema.getDataStructureByReference(a.dataStructure)
                        aa.append(a)

                        allowedValuesText = d.description

                        if d.allowedValues and d.description == "":
                            allowedValuesText = "one of: {}".format(", ".join(["`{}`".format(v) for v in d.allowedValues]))
                        elif d.allowedPattern and d.description == "" and d.baseStructure == "string":
                            allowedValuesText = f"a string with the pattern `{d.allowedPattern}`"

                        fileObject.write("| `{}` | {} | {} | {} |\n".format(a.attributeName, "Required" if not attribute.isOptional else "Optional", allowedValuesText, a.description))

                    fileObject.write("\n")

                else:
                    fileObject.write("None\n\n")

                fileObject.write("### Possible Subelements\n\n")

                ee = []

                if element.subelements:
                    for subelement in element.subelements.elements:
                        e = schema.getElementStructureByReference(subelement.elementReference)
                        ee.append(e)

                        fileObject.write("- &lt;{}&gt;\n".format(e.elementName))

                    fileObject.write("\n")

                else:
                    fileObject.write("None\n\n")

                fileObject.write("### Examples\n\n")
                fileObject.write("Below is shown an example of the `<{}>` element.\n\n".format(element.elementName))
                fileObject.write("```xml\n")

                attributeString = " ".join(["{}=\"{}\"".format(a.attributeName, "..." if a.exampleValue == "" else a.exampleValue) for a in aa])

                if element.isSelfClosing == False:
                    if aa:
                        fileObject.write("<{} {}>\n".format(element.elementName, attributeString))
                    else:
                        fileObject.write("<{}>\n".format(element.elementName))

                    if element.allowedContent == "text only":
                        fileObject.write("    {}\n".format(element.exampleValue))
                    else:
                        for e in ee:
                            if e.isSelfClosing == False:
                                fileObject.write("    <{}></{}>\n".format(e.elementName, e.elementName))
                            else:
                                fileObject.write("    <{} />\n".format(e.elementName, e.elementName))

                    fileObject.write("</{}>\n".format(element.elementName))
                else:
                    if aa:
                        fileObject.write("<{} {} />\n".format(element.elementName, attributeString))
                    else:
                        fileObject.write("<{} />\n".format(element.elementName))

                fileObject.write("```\n\n")


class ExampleFileGenerator(object):
    """
    A class for generating example files that conform to a given schema.

    ...

    To do:

    At the moment this only works for XML schemas - would be nice to get this working for JSON schemas too.
    Would be nice to get this generating invalid XML files too, for automatic testing of schemas.
    """
    def __init__(self):
        pass 

    def generateExampleFiles(self, schema, folderPath):

        os.makedirs(folderPath, exist_ok=True)

        rootElements = schema.getRootElementStructures()

        for rootElement in rootElements:

            filePath = os.path.join(folderPath, "example1.xml")

            e1 = XMLElement(rootElement.elementName)

            self._generateAttributes(rootElement, e1)
            self._generateSubelements(rootElement, e1)

            tree = XMLElementTree(e1)
            indent(tree, space="    ")
            tree.write(filePath, xml_declaration=True, encoding="utf-8", pretty_print=True)

    def _generateAttributes(self, elementStructure, e1):
        for attributeUsageReference in elementStructure.attributes:
            s = attributeUsageReference.attributeStructure

            logger.debug(f"Generating attribute '{s.attributeName}'.")

            if s.dataStructure != None:
                e1.set(s.attributeName, s.dataStructure.metadata.exampleValue)

    def _generateSubelements(self, elementStructure, e1):
        if elementStructure.contentIsSingleValue:
            if elementStructure.valueType != None:
                e1.text = elementStructure.valueType.metadata.exampleValue
            elif elementStructure.metadata.exampleValue != "":
                e1.text = elementStructure.metadata.exampleValue
        if elementStructure.contentIsAnyText:
            e1.text = elementStructure.metadata.exampleValue 

        if isinstance(elementStructure.allowedContent, OrderedStructureList):
            for structure in elementStructure.allowedContent.structures:
                if isinstance(structure, ElementUsageReference):
                    n = 1

                    if structure.maximumNumberOfOccurrences == -1:
                        n = 3
                    elif structure.maximumNumberOfOccurrences <= 3:
                        n = structure.maximumNumberOfOccurrences

                    for x in range(n):
                        e2 = XMLElement(structure.elementStructure.elementName)

                        self._generateAttributes(structure.elementStructure, e2)
                        self._generateSubelements(structure.elementStructure, e2)

                        e1.append(e2)


"""
Functions that allow you to do the export process in a single line.
Best not to use these if you're going to export a large number of schemas.
"""

def exportSchemaAsXSD(schema, versionNumber, filePath):
    """
    Exports the given schema as an XSD document.

    Parameters
    ----------
    schema : Schema
        The schema to export.
    versionNumber : string
        The version number of the schema.
    filePath : string
        The path to which to save the XSD file.

    Returns
    -------
    None
    """

    xsdExporter = XSDExporter()
    xsdExporter.exportSchema(schema, versionNumber, filePath) 

def exportSchemaAsJSONSchema(schema, versionNumber, filePath):
    """
    Exports the given schema as a JSON Schemas document.

    Parameters
    ----------
    schema : Schema
        The schema to export.
    versionNumber : string
        The version number of the schema.
    filePath : string
        The path to which to save the JSON Schemas file.

    Returns
    -------
    None
    """

    jsonSchemasExporter = JSONSchemasExporter()
    jsonSchemasExporter.exportSchema(schema, versionNumber, filePath)

def generateSpecification(schema, filePath):
    """
    Generates a specification / human-readable documentation for the given schema. Some manual editing will be required,
    but this function can save a lot of time.

    Parameters
    ----------
    schema : Schema
        The schema to create a specification for.
    filePath : string
        The file path to which to save the specification.

    Returns
    -------
    None
    """

    specificationGenerator = SpecificationGenerator()
    specificationGenerator.generateSpecification(schema, filePath)

def generateExampleXMLFiles(schema, folderPath):
    """
    Generates example XML files for the given schema. Some manual editing will be required, but this function
    can save time at the start of defining a new format. 

    Parameters
    ----------
    schema : Schema
        The schema to create example files for.
    folderPath : string
        The folder to which to save the example files.

    Returns
    -------
    None
    """

    exampleFileGenerator = ExampleFileGenerator()
    exampleFileGenerator.generateExampleFiles(schema, folderPath)