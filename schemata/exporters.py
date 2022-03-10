import os 
import logging 
import re
from lxml.etree import ElementTree as XMLElementTree, Element as XMLElement, SubElement as XMLSubelement, Comment as XMLComment, QName, indent 
import json 
from structures import * 

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)




class JSONSchemasExporter(object):
    def __init__(self):
        self._js = "https://json-schema.org/draft/2020-12/schema"
        self._id = ""

    def exportSchema(self, schema, versionNumber, filePath):
        logging.debug("Exporting schema for {} as JSON Schema.".format(schema.formatName))

        o1 = {}
        o1["$schema"] = self._js 
        o1["$id"] = self._id 
        o1["title"] = "{} ({})".format(schema.formatName, versionNumber)
        o1["type"] = "object"

        rootObject = schema.getRootObjectStructures()[0]

        self._exportObject(schema, rootObject, o1)

        with open(filePath, "w") as fo:
            json.dump(o1, fo, indent=4)

    def _exportArray(self, schema, _array, jsonObject):
        jsonObject["type"] = "array"

        if _array.itemTypeReference == "string":
            jsonObject["items"] = {"type":"string"}
        elif _array.itemTypeReference == "integer":
            jsonObject["items"] = {"type":"integer"}
        elif _array.itemTypeReference == "decimal":
            jsonObject["items"] = {"type":"decimal"}
        elif _array.itemTypeReference == "boolean":
            jsonObject["items"] = {"type":"boolean"}
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

    def exportSchema(self, schema, versionNumber, filePath):
        xs = self._xs

        logging.debug("Exporting schema for {} as XSD.".format(schema.formatName))

        e1 = XMLElement(QName(xs, "schema"))
        e1.set("elementFormDefault", "qualified")

        if schema.formatName != "":
            c1 = XMLComment(" An XSD file for {} ({}). ".format(schema.formatName, versionNumber))

            e1.append(c1)

        self._exportDataStructures(schema, e1)
        self._exportElementStructures(schema, e1)

        logging.debug("Exporting root elements.")

        roots = schema.getRootElementStructures()

        for root in roots:
            logging.debug("Exporting element <{}>.".format(root.elementName))

            e2 = XMLElement(QName(xs, "element"))
            e2.set("name", root.elementName)
            e2.set("type", self._getXSDTypeName(root))

            e1.append(e2)

        tree = XMLElementTree(e1)
        indent(tree, space="    ")
        tree.write(filePath, xml_declaration=True, encoding="utf-8", pretty_print=True)

    def _exportDataStructures(self, schema, xsdElement):
        xs = self._xs 

        logging.debug("Exporting data structures.")

        dataStructures = schema.getDataStructures()

        for dataStructure in dataStructures:
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
        xs = self._xs 

        logging.debug("Exporting element structures.")

        elementStructures = schema.getElementStructures()

        for elementStructure in elementStructures:
            if not elementStructure.isUsed:
                continue 

            logging.debug("Exporting element structure '{}' <{}>.".format(elementStructure.reference, elementStructure.elementName))

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
        xs = self._xs 

        xsdIndicatorType = "sequence"

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




xsdExporter = XSDExporter()

def exportSchemaAsXSD(schema, versionNumber, filePath):
    xsdExporter.exportSchema(schema, versionNumber, filePath) 

jsonSchemasExporter = JSONSchemasExporter()

def exportSchemaAsJSONSchema(schema, versionNumber, filePath):
    jsonSchemasExporter.exportSchema(schema, versionNumber, filePath)

def generateSpecification(schema, filePath):
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

exampleFileGenerator = ExampleFileGenerator()