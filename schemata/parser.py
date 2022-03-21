import os 
import logging 
import re
from lxml.etree import ElementTree as XMLElementTree, Element as XMLElement, SubElement as XMLSubelement, Comment as XMLComment, QName, indent 
import json 
from schemata.structures import * 

logger = logging.getLogger("schemata.parser")

"""
This module contains the Schemata parser.

This module contains the code that takes Schemata syntax - a relatively compact syntax - and turns it into
a set of objects representing the schema. From there, the schema can be exported to XSD, or Schematron, or
JSON Schemas, or auto-generated documentation, depending on what's relevant.

The parsing is done completely in one step. The parser scans the document and constructs the objects in one go.
"""


class Marker(object):
    def __init__(self):
        self.position = 0

    def copy(self):
        marker = Marker()

        marker.position = self.position

        return marker


def cut(text, startIndex, length=1):
    a = startIndex
    b = startIndex + length
    return text[a:b]


class SchemataParsingError(Exception):
    def __init__(self, message):
        super().__init__(message)


class Parser(object):
    _propertyNameCharacters = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"
    _referenceCharacters = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"
    _operators = ["=", ">", ">=", "<", "<=", "/="]
    _negatedOperators = ["=", "<", "<=", ">", ">=", "/="]
    _propertyNames = [
        "baseType",
        "tagName",
        "allowedPattern",
        "allowedValues",
        "minimumValue",
        "maximumValue",
        "defaultValue",
        "valueType",
        "attributes",
        "allowedContent",
        "itemType",
        "properties",
        "isSelfClosing",
        "lineBreaks"
    ]

    def __init__(self):
        pass 

    def parseSchemaFromFile(self, filePath):
        with open(filePath, "r") as fileObject:
            text = fileObject.read()

            schema = self.parseSchema(text, filePath)

            return schema 

    def parseSchema(self, inputText, filePath = ""):
        logger.debug("Attempting to parse schema.")

        marker = Marker()

        schema = Schema()

        self._parseWhiteSpace(inputText, marker)

        logger.debug("Attempting to parse schema metadata.")

        metadata = self._parseComment(inputText, marker)

        if metadata != None:
            logger.debug("Found metadata comment.")

            m = re.search(r"Format Name:\s*(.+)\n", metadata)

            if m != None:
                schema.formatName = m.group(1).strip()
                logger.debug(f"Got format name '{schema.formatName}'.")

        importStatements = self._parseImportStatements(inputText, marker, schema)

        for i in importStatements:
            path = os.path.join(os.path.dirname(filePath), i)

            if not os.path.exists(path):
                raise Exception(f"'{path}' does not exist.") 

            s = self.parseSchemaFromFile(path)

            schema.dependencies.append(s)

        schema.structures = self._parseStructures(inputText, marker, schema)

        for structure in schema.structures:
            if isinstance(structure, ElementStructure) and isinstance(structure.allowedContent, ElementUsageReference):
                s = structure.allowedContent.elementStructure

                if isinstance(s, DataStructure):
                    structure.valueTypeReference = s.reference
                    ds = DataUsageReference()
                    ds.schema = schema
                    ds.dataStructureReference = s.reference 
                    structure.allowedContent =ds

        listDataStructures = []

        for structure in schema.structures:
            if isinstance(structure, AttributeStructure) and isinstance(structure.dataStructureReference, ListFunction):
                lf = structure.dataStructureReference
                ds1 = lf.dataStructure
                ds1.setIsUsed()

                pattern = ""

                if ds1.allowedValues:
                    pattern = "|".join(ds1.allowedValues)
                elif ds1.allowedPattern != "":
                    pattern = ds1.allowedPattern

                ds2 = DataStructure()
                ds2.schema = schema
                ds2.reference = f"list_of__{ds1.reference}"
                ds2.baseStructureReference = "string"
                ds2.allowedPattern = "({})(\s*{}\s*({}))*".format(pattern, lf.separator, pattern)

                logger.debug("Creating list structure '{}'.".format(ds2.reference))

                structure.dataStructureReference = ds2.reference 

                listDataStructures.append(ds2)

        logger.debug(f"Created {len(listDataStructures)} list data structures.")

        schema.structures += listDataStructures 

        schema.setIsUsed()

        logger.debug("Schema structures: {}".format(", ".join([str(structure) for structure in schema.structures])))

        return schema 

    def _parseImportStatements(self, inputText, marker, schema = None):
        logger.debug("Getting import statements.")

        self._parseWhiteSpace(inputText, marker)

        importStatements = []

        while marker.position < len(inputText):
            i = self._parseImportStatement(inputText, marker, schema)

            if i != None:
                importStatements.append(i) 
            else:
                break

        logger.debug(f"{len(importStatements)} import statements found.")

        return importStatements

    def _parseImportStatement(self, inputText, marker, schema = None):
        logger.debug("Attempting to parse import statement.")

        self._parseWhiteSpace(inputText, marker)

        if cut(inputText, marker.position, 6) == "import":
            marker.position += 6

            self._parseWhiteSpace(inputText, marker)

            path = self._parseString(inputText, marker)

            if path == None or path == "":
                raise SchemataParsingError(f"Expected a path string at {marker.position}.")

            logger.debug(f"Found path '{path}'.")

            return path 

        return None 

    def _parseStructures(self, inputText, marker, schema = None):
        logger.debug("Attempting to parse structures.")

        structures = []
        references = []

        while marker.position < len(inputText):
            self._parseWhiteSpace(inputText, marker)
            self._parseComment(inputText, marker)
            
            structure = self._parseStructure(inputText, marker, schema)

            if structure != None:
                if structure.reference in references:
                    raise SchemataParsingError(f"A structure with the reference '{structure.reference}' has already been defined.")

                structures.append(structure)
                references.append(structure.reference)

        logger.debug(f"Found {len(structures)} structures.")

        return structures

    def _parseStructure(self, inputText, marker, schema = None):
        logger.debug("Attempting to parse structure.")

        self._parseWhiteSpace(inputText, marker)

        if cut(inputText, marker.position, 8) == "dataType":
            marker.position += 8

            logger.debug("Found data structure.")

            dataStructure = self._parseDataStructure(inputText, marker, schema)

            return dataStructure 

        if cut(inputText, marker.position, 9) == "attribute":
            marker.position += 9

            logger.debug("Found attribute structure.")

            attributeStructure = self._parseAttributeStructure(inputText, marker, schema)

            return attributeStructure 

        if cut(inputText, marker.position, 4) == "root":
            marker.position += 4 

            self._parseWhiteSpace(inputText, marker)

            if cut(inputText, marker.position, 7) == "element":
                marker.position += 7

                logger.debug("Found root element structure.")

                elementStructure = self._parseElementStructure(inputText, marker, schema)
                elementStructure.canBeRootElement = True 

                return elementStructure 
            elif cut(inputText, marker.position, 6) == "object":
                marker.position += 6

                logger.debug("Found root object structure.")

                objectStructure = self._parseObjectStructure(inputText, marker, schema)
                objectStructure.canBeRootObject = True 

                return objectStructure 
            else:
                raise SchemataParsingError(f"Expected 'element' keyword at position {marker.position}.")

        if cut(inputText, marker.position, 7) == "element":
            marker.position += 7

            logger.debug("Found element structure.")

            elementStructure = self._parseElementStructure(inputText, marker, schema)

            return elementStructure 

        if cut(inputText, marker.position, 8) == "property":
            marker.position += 8

            logger.debug("Found property structure.")

            propertyStructure = self._parsePropertyStructure(inputText, marker, schema)

            return propertyStructure 

        if cut(inputText, marker.position, 5) == "array":
            marker.position += 5

            logger.debug("Found array structure.")

            arrayStructure = self._parseArrayStructure(inputText, marker, schema)

            return arrayStructure 

        if cut(inputText, marker.position, 6) == "object":
            marker.position += 6

            logger.debug("Found object structure.")

            objectStructure = self._parseObjectStructure(inputText, marker, schema)

            return objectStructure 

        return None

    def _parseDataStructure(self, inputText, marker, schema = None):
        """ Gets any data structure at the current position and returns it.

        Parameters
        ----------
        inputText : str
            The text being parsed
        marker : Marker
            A marker denoting the position at which to start parsing
        schema : Schema
            The schema object being created
        """

        dataStructure = DataStructure()
        dataStructure.schema = schema 

        # Get the reference.
        self._parseWhiteSpace(inputText, marker)        
        reference = self._parseReference(inputText, marker)
        self._parseWhiteSpace(inputText, marker)

        dataStructure.reference = reference 

        # Expect the opening bracket.
        if cut(inputText, marker.position, 1) == "{":
            marker.position += 1
        else:
            raise SchemataParsingError("Expected '{{' at position {}.".format(marker.position))

        self._parseWhiteSpace(inputText, marker) 

        # Get the metadata.
        metadata = self._parseComment(inputText, marker)

        if metadata != None:
            m1 = re.search(r"Description:\s*(.+)\n", metadata)
            m2 = re.search(r"Example Value:\s*(.+)\n", metadata)

            if m1 != None:
                dataStructure.metadata.description = m1.group(1).strip()

            if m2 != None:
                dataStructure.metadata.exampleValue = m2.group(1).strip()

        self._parseWhiteSpace(inputText, marker) 

        # Step through the text looking for properties.
        while marker.position < len(inputText):
            p = self._parseProperty(inputText, marker, schema)

            if p == None:
                break
            else:
                if p[0] == "baseType":
                    dataStructure.baseStructureReference = p[1]
                if p[0] == "allowedPattern":
                    dataStructure.allowedPattern = p[1]
                if p[0] == "allowedValues":
                    dataStructure.allowedValues = p[1] 
                if p[0] == "minimumValue":
                    dataStructure.minimumValue = p[1]
                if p[0] == "maximumValue":
                    dataStructure.maximumValue = p[1]

        self._parseWhiteSpace(inputText, marker)

        # Expect the closing bracket.
        if cut(inputText, marker.position, 1) == "}":
            marker.position += 1
        else:
            raise SchemataParsingError("Expected '}}' at position {}.".format(marker.position))

        return dataStructure

    def _parseAttributeStructure(self, inputText, marker, schema = None):
        """ Gets any attribute structure at the current position and returns it.

        Parameters
        ----------
        inputText : str
            The text being parsed
        marker : Marker
            A marker denoting the position at which to start parsing
        schema : Schema
            The schema object being created
        """

        attributeStructure = AttributeStructure()
        attributeStructure.schema = schema

        # Get the reference.
        self._parseWhiteSpace(inputText, marker)
        reference = self._parseReference(inputText, marker)
        self._parseWhiteSpace(inputText, marker)

        attributeStructure.reference = reference 

        # Expect the opening bracket.
        if cut(inputText, marker.position, 1) == "{":
            marker.position += 1
        else:
            raise SchemataParsingError("Expected '{{' at position {}.".format(marker.position))

        self._parseWhiteSpace(inputText, marker) 

        # Get the metadata.
        metadata = self._parseComment(inputText, marker)

        if metadata != None:
            m1 = re.search(r"Description:\s*(.+)\n", metadata)
            m2 = re.search(r"Example Value:\s*(.+)\n", metadata)

            if m1 != None:
                attributeStructure.metadata.description = m1.group(1).strip()

            if m2 != None:
                attributeStructure.metadata.exampleValue = m2.group(1).strip()

        self._parseWhiteSpace(inputText, marker) 

        # Step through the text looking for properties.
        while marker.position < len(inputText):
            p = self._parseProperty(inputText, marker, schema)

            if p == None:
                break
            else:
                if p[0] == "baseType":
                    attributeStructure.baseStructureReference = p[1]
                if p[0] == "tagName":
                    attributeStructure.attributeName = p[1]
                if p[0] == "valueType":
                    attributeStructure.dataStructureReference = p[1]
                if p[0] == "defaultValue":
                    attributeStructure.defaultValue = p[1]

        self._parseWhiteSpace(inputText, marker)

        # Expect the closing bracket.
        if cut(inputText, marker.position, 1) == "}":
            marker.position += 1
        else:
            raise SchemataParsingError("Expected '}}' at position {}.".format(marker.position))

        # If the attribute name has not been set explicitly, use the attribute structure reference.
        # This allows .schema files to be terse.
        if attributeStructure.attributeName == "":
            attributeStructure.attributeName = attributeStructure.reference 

        return attributeStructure 

    def _parseElementStructure(self, inputText, marker, schema = None):
        """ Gets any element structure at the current position and returns it.

        Parameters
        ----------
        inputText : str
            The text being parsed
        marker : Marker
            A marker denoting the position at which to start parsing
        schema : Schema
            The schema object being created
        """

        elementStructure = ElementStructure()
        elementStructure.schema = schema 

        # Get the reference.
        self._parseWhiteSpace(inputText, marker)
        reference = self._parseReference(inputText, marker)
        self._parseWhiteSpace(inputText, marker)

        elementStructure.reference = reference 

        # Expect the opening bracket.
        if cut(inputText, marker.position, 1) == "{":
            marker.position += 1
        else:
            raise SchemataParsingError("Expected '{{' at position {}.".format(marker.position))

        self._parseWhiteSpace(inputText, marker)

        # Get the metadata.
        metadata = self._parseComment(inputText, marker)

        if metadata != None:
            m1 = re.search(r"Description:\s*(.+)\n", metadata)
            m2 = re.search(r"Example Value:\s*(.+)\n", metadata)

            if m1 != None:
                elementStructure.metadata.description = m1.group(1).strip()

            if m2 != None:
                elementStructure.metadata.exampleValue = m2.group(1).strip()

        self._parseWhiteSpace(inputText, marker) 

        # Step through the text looking for properties.
        while marker.position < len(inputText):
            p = self._parseProperty(inputText, marker, schema)

            if p == None:
                break
            else:
                if p[0] == "baseType":
                    elementStructure.baseStructureReference = p[1]
                if p[0] == "tagName":
                    elementStructure.elementName = p[1]
                if p[0] == "attributes":
                    elementStructure.attributes = p[1]
                if p[0] == "allowedContent":
                    elementStructure.allowedContent = p[1]
                if p[0] == "isSelfClosing":
                    elementStructure.isSelfClosing = p[1]
                if p[0] == "lineBreaks":
                    elementStructure.lineBreaks = p[1]

        self._parseWhiteSpace(inputText, marker)

        # Expect the closing bracket.
        if cut(inputText, marker.position, 1) == "}":
            marker.position += 1
        else:
            raise SchemataParsingError("Expected '}}' at position {}.".format(marker.position))

        # If the element name has not been set explicitly, use the element structure reference.
        # This allows .schema files to be terse.
        if elementStructure.elementName == "":
            elementStructure.elementName = elementStructure.reference 

        return elementStructure 

    def _parsePropertyStructure(self, inputText, marker, schema = None):
        """ Gets any property structure at the current position and returns it.

        Parameters
        ----------
        inputText : str
            The text being parsed
        marker : Marker
            A marker denoting the position at which to start parsing
        schema : Schema
            The schema object being created
        """

        propertyStructure = PropertyStructure()
        propertyStructure.schema = schema

        # Get the reference.
        self._parseWhiteSpace(inputText, marker)
        reference = self._parseReference(inputText, marker)
        self._parseWhiteSpace(inputText, marker)

        propertyStructure.reference = reference 

        # Expect the opening bracket.
        if cut(inputText, marker.position, 1) == "{":
            marker.position += 1
        else:
            raise SchemataParsingError("Expected '{{' at position {}.".format(marker.position))

        self._parseWhiteSpace(inputText, marker) 

        # Get the metadata.
        metadata = self._parseComment(inputText, marker)

        if metadata != None:
            m1 = re.search(r"Description:\s*(.+)\n", metadata)
            m2 = re.search(r"Example Value:\s*(.+)\n", metadata)

            if m1 != None:
                propertyStructure.metadata.description = m1.group(1).strip()

            if m2 != None:
                propertyStructure.metadata.exampleValue = m2.group(1).strip()

        self._parseWhiteSpace(inputText, marker) 

        # Step through the text looking for properties.
        while marker.position < len(inputText):
            p = self._parseProperty(inputText, marker, schema)

            if p == None:
                break
            else:
                if p[0] == "tagName":
                    propertyStructure.propertyName = p[1]
                if p[0] == "valueType":
                    propertyStructure.valueTypeReference = p[1]

        self._parseWhiteSpace(inputText, marker)

        # Expect the closing bracket.
        if cut(inputText, marker.position, 1) == "}":
            marker.position += 1
        else:
            raise SchemataParsingError("Expected '}}' at position {}.".format(marker.position))

        # If the property name has not been set explicitly, use the property structure reference.
        # This allows .schema files to be terse.
        if propertyStructure.propertyName == "":
            propertyStructure.propertyName = propertyStructure.reference 

        return propertyStructure 

    def _parseArrayStructure(self, inputText, marker, schema = None):
        """ Gets any array structure at the current position and returns it.

        Parameters
        ----------
        inputText : str
            The text being parsed
        marker : Marker
            A marker denoting the position at which to start parsing
        schema : Schema
            The schema object being created
        """

        arrayStructure = ArrayStructure()
        arrayStructure.schema = schema 

        # Get the reference.
        self._parseWhiteSpace(inputText, marker)
        reference = self._parseReference(inputText, marker)
        self._parseWhiteSpace(inputText, marker)

        arrayStructure.reference = reference 

        # Expect the opening bracket.
        if cut(inputText, marker.position, 1) == "{":
            marker.position += 1
        else:
            raise SchemataParsingError("Expected '{{' at position {}.".format(marker.position))

        self._parseWhiteSpace(inputText, marker)

        # Get the metadata.
        metadata = self._parseComment(inputText, marker)

        if metadata != None:
            m1 = re.search(r"Description:\s*(.+)\n", metadata)
            m2 = re.search(r"Example Value:\s*(.+)\n", metadata)

            if m1 != None:
                arrayStructure.metadata.description = m1.group(1).strip()

            if m2 != None:
                arrayStructure.metadata.exampleValue = m2.group(1).strip()

        self._parseWhiteSpace(inputText, marker) 

        # Step through the text looking for properties.
        while marker.position < len(inputText):
            p = self._parseProperty(inputText, marker, schema)

            if p == None:
                break
            else:
                if p[0] == "baseType":
                    arrayStructure.baseStructureReference = p[1]
                if p[0] == "itemType":
                    arrayStructure.itemTypeReference = p[1]

        self._parseWhiteSpace(inputText, marker)

        # Expect the closing bracket.
        if cut(inputText, marker.position, 1) == "}":
            marker.position += 1
        else:
            raise SchemataParsingError("Expected '}}' at position {}.".format(marker.position))

        return arrayStructure 

    def _parseObjectStructure(self, inputText, marker, schema = None):
        """ Gets any object structure at the current position and returns it.

        Parameters
        ----------
        inputText : str
            The text being parsed
        marker : Marker
            A marker denoting the position at which to start parsing
        schema : Schema
            The schema object being created
        """

        objectStructure = ObjectStructure()
        objectStructure.schema = schema 

        # Get the reference.
        self._parseWhiteSpace(inputText, marker)
        reference = self._parseReference(inputText, marker)
        self._parseWhiteSpace(inputText, marker)

        objectStructure.reference = reference 

        # Expect the opening bracket.
        if cut(inputText, marker.position, 1) == "{":
            marker.position += 1
        else:
            raise SchemataParsingError("Expected '{{' at position {}.".format(marker.position))

        self._parseWhiteSpace(inputText, marker)

        # Get the metadata.
        metadata = self._parseComment(inputText, marker)

        if metadata != None:
            m1 = re.search(r"Description:\s*(.+)\n", metadata)
            m2 = re.search(r"Example Value:\s*(.+)\n", metadata)

            if m1 != None:
                objectStructure.metadata.description = m1.group(1).strip()

            if m2 != None:
                objectStructure.metadata.exampleValue = m2.group(1).strip()

        self._parseWhiteSpace(inputText, marker) 

        # Step through the text looking for properties.
        while marker.position < len(inputText):
            p = self._parseProperty(inputText, marker, schema)

            if p == None:
                break
            else:
                if p[0] == "baseType":
                    objectStructure.baseStructureReference = p[1]
                if p[0] == "properties":
                    objectStructure.properties = p[1]

        self._parseWhiteSpace(inputText, marker)

        # Expect the closing bracket.
        if cut(inputText, marker.position, 1) == "}":
            marker.position += 1
        else:
            raise SchemataParsingError("Expected '}}' at position {}.".format(marker.position))

        return objectStructure 

    def _parseProperty(self, inputText, marker, schema = None):
        """ Gets any property at the current position and returns it.

        Parameters
        ----------
        inputText : str
            The text being parsed
        marker : Marker
            A marker denoting the position at which to start parsing
        schema : Schema
            The schema object being created
        """

        logger.debug("Attempting to parse structure property.")

        self._parseWhiteSpace(inputText, marker)

        # Get the property name.
        propertyName = self._parsePropertyName(inputText, marker)

        # If there is no property name, there is no property, so return None.
        if propertyName == None:
            return None 

        logger.debug(f"Found property name '{propertyName}'.")

        # If the property name is not a Schemata property name, raise an exception.
        if propertyName not in Parser._propertyNames:
            raise SchemataParsingError(f"'{propertyName}' is not a valid Schemata property name.")

        self._parseWhiteSpace(inputText, marker)

        # A colon must follow for it to be a property.
        if cut(inputText, marker.position) == ":":
            marker.position += 1
        else:
            return None 

        self._parseWhiteSpace(inputText, marker)
        
        propertyValue = None 

        # Get the property value. If the type of the property value is wrong, raise an exception.

        if propertyName == "baseType":
            propertyValue = self._parseReference(inputText, marker)

            if propertyValue == None:
                raise SchemataParsingError(f"Expected a reference for property '{propertyName}'.")

        if propertyName == "tagName":
            propertyValue = self._parseString(inputText, marker)

            if propertyValue == None:
                raise SchemataParsingError(f"Expected a string for property '{propertyName}'.")

        if propertyName == "allowedPattern":
            propertyValue = self._parseString(inputText, marker)

            if propertyValue == None:
                raise SchemataParsingError(f"Expected a string for property '{propertyName}'.")
        
        if propertyName == "allowedValues":
            propertyValue = self._parseList(inputText, marker)

            if propertyValue == None:
                raise SchemataParsingError(f"Expected a list of values for property '{propertyName}'.")

        if propertyName == "minimumValue":
            propertyValue = self._parseInteger(inputText, marker)

            if propertyValue == None:
                raise SchemataParsingError(f"Expected an integer for property '{propertyName}'.")

        if propertyName == "maximumValue":
            propertyValue = self._parseInteger(inputText, marker)

            if propertyValue == None:
                raise SchemataParsingError(f"Expected an integer for property '{propertyName}'.")

        if propertyName == "defaultValue":
            propertyValue = self._parseString(inputText, marker)

            if propertyValue == None:
                propertyValue = self._parseInteger(inputText, marker)

            if propertyValue == None:
                propertyValue = self._parseBoolean(inputText, marker)

            if propertyValue == None:
                raise SchemataParsingError(f"Expected a string, integer, or boolean for property '{propertyName}'.")
        
        if propertyName == "valueType":
            propertyValue = self._parseListFunction(inputText, marker, schema)

            if propertyValue == None:
                propertyValue = self._parseReference(inputText, marker)

            if propertyValue == None:
                raise SchemataParsingError(f"Expected a reference for property '{propertyName}'.")
        
        if propertyName == "itemType":
            propertyValue = self._parseReference(inputText, marker)

            if propertyValue == None:
                raise SchemataParsingError(f"Expected a reference for property '{propertyName}'.")

        if propertyName == "attributes":
            propertyValue = self._parseList(inputText, marker, "attributeUsageReference", schema)

            if propertyValue == None:
                raise SchemataParsingError(f"Expected an attribute usage reference list for property '{propertyName}'.")

        if propertyName == "properties":
            propertyValue = self._parseList(inputText, marker, "propertyUsageReference", schema)

            if propertyValue == None:
                raise SchemataParsingError(f"Expected a property usage reference list for property '{propertyName}'.")

        if propertyName == "allowedContent":
            propertyValue = self._parseSubelementUsages(inputText, marker, schema)

            if propertyValue == None:
                raise SchemataParsingError(f"Expected a structure usage reference or structure list for property '{propertyName}'.")

        if propertyName == "isSelfClosing":
            propertyValue = self._parseBoolean(inputText, marker)

            if propertyValue == None:
                raise SchemataParsingError(f"Expected a boolean for property '{propertyName}'.")

        if propertyName == "lineBreaks":
            propertyValue = self._parseList(inputText, marker, "integer")

            if propertyValue == None:
                raise SchemataParsingError(f"Expected a list of integers for property '{propertyName}'.")

        if propertyValue == None:
            raise SchemataParsingError(f"Expected a value for property '{propertyName}'.")

        self._parseWhiteSpace(inputText, marker)

        logger.debug("Found property value '{}'.".format(propertyValue))

        # Expect semi-colon.
        if cut(inputText, marker.position) == ";":
            marker.position += 1
        else:
            raise SchemataParsingError(f"Expected ';' at position {marker.position}.")

        return (propertyName, propertyValue)  

    def _parseListFunction(self, inputText, marker, schema = None):
        """ Gets any list function at the current position and returns it.

        List functions can be used to automatically create new data types where the data structure is a list
        of another data type's enumerations. This prevents the user from having to write complex patterns
        in the .schema file.

        Parameters
        ----------
        inputText : str
            The text being parsed
        marker : Marker
            A marker denoting the position at which to start parsing
        schema : Schema
            The schema object being created
        """

        logger.debug("Attempting to parse list function.")

        self._parseWhiteSpace(inputText, marker)

        # List functions must start with 'list'.
        if cut(inputText, marker.position, 4) == "list":
            marker.position += 4
        else:
            return None 

        self._parseWhiteSpace(inputText, marker)

        # Expect the opening bracket.
        if cut(inputText, marker.position, 1) == "(":
            marker.position += 1
        else:
            raise SchemataParsingError(f"Expected '(' at position {marker.position}.")

        self._parseWhiteSpace(inputText, marker)

        # Expect a reference.
        reference = self._parseReference(inputText, marker)

        if reference == None:
            raise SchemataParsingError(f"Expected a reference at position {marker.position}.")

        self._parseWhiteSpace(inputText, marker)

        # Expect a comma.
        if cut(inputText, marker.position, 1) == ",":
            marker.position += 1
        else:
            raise SchemataParsingError(f"Expected ',' at position {marker.position}.")

        self._parseWhiteSpace(inputText, marker)

        # Expect a string that denotes the separator.
        separator = self._parseString(inputText, marker)

        if separator == None:
            raise SchemataParsingError(f"Expected a string at position {marker.position}.")

        self._parseWhiteSpace(inputText, marker)

        # Expect the closing bracket.
        if cut(inputText, marker.position, 1) == ")":
            marker.position += 1
        else:
            raise SchemataParsingError(f"Expected ')' at position {marker.position}.")

        listFunction = ListFunction(reference, separator)
        listFunction.schema = schema 

        logger.debug(f"Found list function: {listFunction}.")

        return listFunction

    def _parseSubelementUsages(self, inputText, marker, schema = None):
        """ Gets any subelement usage at the current position and returns it.

        A subelement usage can include an element usage reference, a data usage reference, an any elements usage reference,
        an any text usage reference, an ordered structure list, an unordered structure list, or a structure choice.

        Parameters
        ----------
        inputText : str
            The text being parsed
        marker : Marker
            A marker denoting the position at which to start parsing
        schema : Schema
            The schema object being created
        """

        # Look for the different things that can be subelement usages, and return if found.

        item = self._parseElementUsageReference(inputText, marker, schema)

        if item != None:
            return item 

        logger.debug("Didn't find element usage reference.")

        item = self._parseAnyElementsUsageReference(inputText, marker, schema)

        if item != None:
            return item 

        logger.debug("Didn't find any elements usage reference.")

        item = self._parseAnyTextUsageReference(inputText, marker, schema)

        if item != None:
            return item 

        logger.debug("Didn't find any text usage reference.")

        item = self._parseSubelementList(inputText, marker, schema)

        if item != None:
            return item 

        logging.debug("Didn't find subelement list.")

        return None 

    def _parseSubelementList(self, inputText, marker, schema = None):
        """ Gets any subelement / substructure list at the current position and returns it.

        Parameters
        ----------
        inputText : str
            The text being parsed
        marker : Marker
            A marker denoting the position at which to start parsing
        schema : Schema
            The schema object being created
        """

        logger.debug("Attempting to parse a subelement list.")

        # Copy the marker, as we're going to use other functions that will edit the marker.
        m = marker.copy()

        self._parseWhiteSpace(inputText, m)
        self._parseComment(inputText, m)
        self._parseWhiteSpace(inputText, m)

        # The bracket type and the separator type determine what kind of list this is.
        bracketType = ""
        separatorType = "comma"

        if cut(inputText, m.position) == "{":
            bracketType = "recurve"
            m.position += 1
        elif cut(inputText, m.position) == "[":
            bracketType = "square"
            m.position += 1
        else:
            return None 

        logger.debug(f"Identified bracket type: {bracketType}.")

        self._parseWhiteSpace(inputText, m)
        self._parseComment(inputText, m)
        self._parseWhiteSpace(inputText, m)

        items = []
        n = 0

        # Step through the text looking for list items.
        while m.position < len(inputText):
            self._parseWhiteSpace(inputText, m)
            self._parseComment(inputText, m)
            self._parseWhiteSpace(inputText, m)

            # There should be a separator character between each list item.
            if n > 0:
                c = cut(inputText, m.position)

                # The first separator used sets up what separator to expect for the rest of the list.
                if n == 1:
                    if c == ",":
                        separatorType = "comma"
                        m.position += 1
                    elif c == "/":
                        separatorType = "slash"

                        # Slashes can only be used with recurve brackets.
                        if bracketType == "square":
                            raise SchemataParsingError(f"Expected ',' at position {m.position}.")

                        m.position += 1

                elif n > 1:
                    if (separatorType == "comma" and c == ",") or (separatorType == "slash" and c == "/"):
                        m.position += 1
                    elif (separatorType == "comma" and c == "/") or (separatorType == "slash" and c == ","):
                        # If the separator type is not consistent throughout the list, raise an exception.
                        raise SchemataParsingError(f"Separators must be the same throughout a list (position {m.position}).")
                    else:
                        break
            
            self._parseWhiteSpace(inputText, m)
            self._parseComment(inputText, m)
            self._parseWhiteSpace(inputText, m)

            # Try to get an item.
            item = self._parseSubelementUsages(inputText, m, schema)

            # If no item is found, break the loop.
            if item == None:
                break 

            items.append(item)

            n += 1

        logger.debug(f"Identified separator type: {separatorType}.")
        logger.debug(f"List: {items}.")

        self._parseWhiteSpace(inputText, m)
        self._parseComment(inputText, m)
        self._parseWhiteSpace(inputText, m)

        # Check for closing bracket.
        c = cut(inputText, m.position)

        if bracketType == "recurve" and c == "}":
            m.position += 1
        elif bracketType == "square" and c == "]":
            m.position += 1
        else:
            # If no closing bracket or the wrong closing bracket is found, raise an exception.
            raise SchemataParsingError(f"Expected closing bracket at position {m.position}.")

        # Make the list object.
        if bracketType == "square" and separatorType == "comma":
            l = OrderedStructureList()
            l.schema = schema
            l.structures = items 
        elif bracketType == "recurve" and separatorType == "comma":
            l = UnorderedStructureList()
            l.schema = schema
            l.structures = items 
        elif bracketType == "recurve" and separatorType == "slash":
            l = StructureChoice()
            l.schema = schema
            l.structures = items 
        else:
            return None 

        logger.debug(f"Found subelement list {l}.")

        # Update the original marker.
        marker.position = m.position

        return l

    def _parseAttributeUsageReference(self, inputText, marker, schema = None):
        """ Gets an attribute usage reference at the current position and returns it.

        Parameters
        ----------
        inputText : str
            The text being parsed
        marker : Marker
            A marker denoting the position at which to start parsing
        schema : Schema
            The schema object being created
        """

        logger.debug("Attempting to parse attribute usage reference.")

        # First get the reference.
        self._parseWhiteSpace(inputText, marker)
        attributeStructureReference = self._parseReference(inputText, marker)
        self._parseWhiteSpace(inputText, marker)

        if attributeStructureReference == None:
            return None 

        attributeUsageReference = AttributeUsageReference()
        attributeUsageReference.schema = schema 
        attributeUsageReference.attributeStructureReference = attributeStructureReference 

        # Get the information in brackets, if there is any.
        if cut(inputText, marker.position) == "(":
            marker.position += 1

            self._parseWhiteSpace(inputText, marker)

            # Work out if this is an optional attribute.
            if cut(inputText, marker.position, 8) == "optional":
                marker.position += 8

                attributeUsageReference.isOptional = True 

                self._parseWhiteSpace(inputText, marker)

                # If there's not a closing bracket, raise an exception. 
                if cut(inputText, marker.position) == ")":
                    marker.position += 1
                else:
                    raise SchemataParsingError(f"Expected ')' at position {marker.position}.")
            else:
                # If there's nothing in the brackets, raise an exception. 
                raise SchemataParsingError(f"Expected keyword at position {marker.position}.")

        return attributeUsageReference 

    def _parseElementUsageReference(self, inputText, marker, schema = None):
        """ Gets an element usage reference at the current position and returns it.

        This will also pick up data usage references, as the two are indistinguishable. Sorting the element usage
        references from the data usage references is dealt with later in the parsing process.

        Parameters
        ----------
        inputText : str
            The text being parsed
        marker : Marker
            A marker denoting the position at which to start parsing
        schema : Schema
            The schema object being created
        """

        logger.debug("Attempting to parse element usage reference.")

        # First get the reference.
        self._parseWhiteSpace(inputText, marker)
        elementStructureReference = self._parseReference(inputText, marker)
        self._parseWhiteSpace(inputText, marker)

        if elementStructureReference == None:
            return None 

        elementUsageReference = ElementUsageReference()
        elementUsageReference.schema = schema 
        elementUsageReference.elementStructureReference = elementStructureReference  

        # Get the information in the brackets, if there is any.
        if cut(inputText, marker.position) == "(":
            marker.position += 1

            self._parseWhiteSpace(inputText, marker)

            elementUsageReference.minimumNumberOfOccurrences = 0
            elementUsageReference.maximumNumberOfOccurrences = -1

            nExpression = self._parseNExpression(inputText, marker)

            if nExpression != None:
                elementUsageReference.nExpression = nExpression 

                # If there's not a closing bracket, raise an exception.
                if cut(inputText, marker.position) == ")":
                    marker.position += 1
                else:
                    raise SchemataParsingError(f"Expected ')' at position {marker.position}.")

            elif cut(inputText, marker.position, 8) == "optional":
                marker.position += 8

                elementUsageReference.nExpression = [(">=", 0), ("<=", 1)]

                self._parseWhiteSpace(inputText, marker)

                # If there's not a closing bracket, raise an exception.
                if cut(inputText, marker.position) == ")":
                    marker.position += 1
                else:
                    raise SchemataParsingError(f"Expected ')' at position {marker.position}.")
            else:
                # If there's nothing in the brackets, raise an exception.
                raise SchemataParsingError(f"Expected expression or keyword at position {marker.position}.")

        # Apply the n-expression. 
        if elementUsageReference.nExpression != None:
            for comparison in elementUsageReference.nExpression:
                if comparison[0] == ">=":
                    elementUsageReference.minimumNumberOfOccurrences = comparison[1]
                if comparison[0] == ">":
                    elementUsageReference.minimumNumberOfOccurrences = comparison[1] + 1
                if comparison[0] == "<=":
                    elementUsageReference.maximumNumberOfOccurrences = comparison[1]
                if comparison[0] == "<":
                    elementUsageReference.maximumNumberOfOccurrences = comparison[1] - 1
                if comparison[0] == "=":
                    elementUsageReference.minimumNumberOfOccurrences = comparison[1]
                    elementUsageReference.maximumNumberOfOccurrences = comparison[1]

        return elementUsageReference 

    def _parsePropertyUsageReference(self, inputText, marker, schema = None):
        """ Gets a property usage reference at the current position and returns it.

        Parameters
        ----------
        inputText : str
            The text being parsed
        marker : Marker
            A marker denoting the position at which to start parsing
        schema : Schema
            The schema object being created
        """

        logger.debug("Attempting to parse property usage reference.")

        # First get the reference.
        self._parseWhiteSpace(inputText, marker)
        propertyStructureReference = self._parseReference(inputText, marker)
        self._parseWhiteSpace(inputText, marker)

        if propertyStructureReference == None:
            return None 

        propertyUsageReference = PropertyUsageReference()
        propertyUsageReference.schema = schema 
        propertyUsageReference.propertyStructureReference = propertyStructureReference 

        # Get the information in brackets, if there is any.
        if cut(inputText, marker.position) == "(":
            marker.position += 1

            self._parseWhiteSpace(inputText, marker)

            # Work out if this is an optional attribute.
            if cut(inputText, marker.position, 8) == "optional":
                marker.position += 8

                propertyUsageReference.isOptional = True 

                self._parseWhiteSpace(inputText, marker)

                # If there's not a closing bracket, raise an exception. 
                if cut(inputText, marker.position) == ")":
                    marker.position += 1
                else:
                    raise SchemataParsingError(f"Expected ')' at position {marker.position}.")
            else:
                # If there's nothing in the brackets, raise an exception. 
                raise SchemataParsingError(f"Expected keyword at position {marker.position}.")

        return propertyUsageReference 

    def _parseAnyAttributesUsageReference(self, inputText, marker, schema = None):
        """ Gets an any attributes usage reference at the current position and returns it.

        Parameters
        ----------
        inputText : str
            The text being parsed
        marker : Marker
            A marker denoting the position at which to start parsing
        schema : Schema
            The schema object being created
        """

        if cut(inputText, marker.position, 16) == "*any attributes*":
            marker.position += 16

            ur = AnyAttributesUsageReference()
            ur.schema = schema 

            return schema

        return None

    def _parseAnyElementsUsageReference(self, inputText, marker, schema = None):
        """ Gets an any elements usage reference at the current position and returns it.

        Parameters
        ----------
        inputText : str
            The text being parsed
        marker : Marker
            A marker denoting the position at which to start parsing
        schema : Schema
            The schema object being created
        """

        if cut(inputText, marker.position, 14) == "*any elements*":
            marker.position += 14

            ur = AnyElementsUsageReference()
            ur.schema = schema

            return ur

        return None

    def _parseAnyTextUsageReference(self, inputText, marker, schema = None):
        """ Gets an any text usage reference at the current position and returns it.

        Parameters
        ----------
        inputText : str
            The text being parsed
        marker : Marker
            A marker denoting the position at which to start parsing
        schema : Schema
            The schema object being created
        """

        if cut(inputText, marker.position, 10) == "*any text*":
            marker.position += 10

            ur = AnyTextUsageReference()
            ur.schema = schema

            return ur

        return None 

    def _parseAnyPropertiesUsageReference(self, inputText, marker, schema = None):
        """ Gets an any properties usage reference at the current position and returns it.

        Parameters
        ----------
        inputText : str
            The text being parsed
        marker : Marker
            A marker denoting the position at which to start parsing
        schema : Schema
            The schema object being created
        """

        if cut(inputText, marker.position, 16) == "*any properties*":
            marker.position += 16

            ur = AnyPropertiesUsageReference()
            ur.schema = schema 

            return schema

        return None

    def _parseNExpression(self, inputText, marker):
        """ Gets any n-expression (an expression of the form 'n > 0' or '0 > n > 3') at the current position and returns it.

        Parameters
        ----------
        inputText : str
            The text being parsed
        marker : Marker
            A marker denoting the position at which to start parsing
        """

        logger.debug("Attempting to parse n-expression.")

        # Start by trying to find something of the form '0 <'.
        self._parseWhiteSpace(inputText, marker)
        n1 = self._parseInteger(inputText, marker)
        o1 = None 
        self._parseWhiteSpace(inputText, marker)

        if n1 != None:
            o1 = self._parseOperator(inputText, marker)

            # If the expression starts with a number, an operator must follow.
            if o1 == None:
                raise SchemataParsingError(f"Expected an operator at position {marker.position}.")

        self._parseWhiteSpace(inputText, marker)

        # Check for the variable - 'n'.
        if cut(inputText, marker.position) == "n":
            marker.position += 1
        else:
            # If nothing has been found so far, then there is no n-expression, so return None. 
            # If a number and operator have been found, but not an 'n', then the syntax is wrong, so raise an exception.
            if n1 == None and o1 == None:
                return None 
            else:
                raise SchemataParsingError(f"Expected 'n' at position {marker.position}.")

        # Look for an operator and number after the 'n'.
        self._parseWhiteSpace(inputText, marker)
        o2 = self._parseOperator(inputText, marker)

        if o2 == None:
            raise SchemataParsingError(f"Expected an operator at position {marker.position}.")

        self._parseWhiteSpace(inputText, marker)
        n2 = self._parseInteger(inputText, marker)

        if n2 == None:
            raise SchemataParsingError(f"Expected a number at position {marker.position}.")

        e = []

        # Operators before the 'n' must be reversed.
        if n1 != None and o1 != None:
            i = self._operators.index(o1)
            o1b = self._negatedOperators[i]
            e += [(o1b, n1)]

        e += [(o2, n2)]

        return e      

    def _parseList(self, inputText, marker, objectType = "string", schema = None):
        """ Gets any list (of strings, integers, booleans, et cetera) at the current position and returns it.

        Parameters
        ----------
        inputText : str
            The text being parsed
        marker : Marker
            A marker denoting the position at which to start parsing
        objectType : str 
            The type of object to expect in the list
        """

        logger.debug("Attempting to parse list.")

        items = []
        n = 0

        # Keep trying to find items in the list until you find something that's not a valid list item.
        while marker.position < len(inputText):
            self._parseWhiteSpace(inputText, marker)

            # Expect a comma between each of the items in the list.
            if n > 0:
                if cut(inputText, marker.position) == ",":
                    marker.position += 1
                else:
                    break
            
            self._parseWhiteSpace(inputText, marker)

            item = None

            # Check to see if the expected object is present.
            if objectType == "string":
                item = self._parseString(inputText, marker)
            if objectType == "integer":
                item = self._parseInteger(inputText, marker)
            if objectType == "boolean":
                item = self._parseBoolean(inputText, marker)
            if objectType == "attributeUsageReference":
                item = self._parseAttributeUsageReference(inputText, marker, schema)
            if objectType == "propertyUsageReference":
                item = self._parsePropertyUsageReference(inputText, marker, schema)

            # If an item of the right type is not found, break the loop.
            if item == None:
                break 

            items.append(item)

            n += 1

        # If no items were found, no list was found, so return None.
        if n == 0:
            return None 

        logger.debug(f"Found list {items}.")

        return items

    # Parsing of basic structures starts here.

    def _parsePropertyName(self, inputText, marker):
        """ Gets any property name at the current position and returns it.

        Parameters
        ----------
        inputText : str
            The text being parsed
        marker : Marker
            A marker denoting the position at which to start parsing
        """

        logger.debug("Attempting to parse property name.")

        t = ""

        # Step through the text and check if the current character is a valid property name character.
        while marker.position < len(inputText):
            c = cut(inputText, marker.position)

            # If the current character is a valid property name character, add it to the temporary variable. Otherwise, break the loop.
            if c in Parser._propertyNameCharacters:
                t += c
                marker.position += 1
            else:
                break

        # If no property name was found, return None.
        if len(t) == 0:
            return None 

        logger.debug(f"Found property name '{t}'.")

        return t 

    def _parseReference(self, inputText, marker):
        """ Gets any reference at the current position and returns it.

        Parameters
        ----------
        inputText : str
            The text being parsed
        marker : Marker
            A marker denoting the position at which to start parsing
        """

        t = ""

        # Step through the text to see if each character is a valid reference character.
        while marker.position < len(inputText):
            c = cut(inputText, marker.position)

            # If the current character is a valid reference character, add it to the temporary variable. Otherwise, break the loop.
            if c in Parser._referenceCharacters:
                t += c
                marker.position += 1
            else:
                break

        # If nothing was found, return None.
        if len(t) == 0:
            return None

        logger.debug(f"Found reference '{t}'.")

        return t 

    def _parseOperator(self, inputText, marker):
        """ Gets any operator at the current position and returns it.

        Parameters
        ----------
        inputText : str
            The text being parsed
        marker : Marker
            A marker denoting the position at which to start parsing
        """

        # Sort the operators so that we check for the longest one first.
        operators = sorted(self._operators, key= lambda o: len(o), reverse=True)

        # Go through the list of operators.
        for operator in operators:
            # Check if the operator is at the current position.
            if cut(inputText, marker.position, len(operator)) == operator:
                marker.position += len(operator)

                return operator

        # If no operator is found, return None.
        return None 

    def _parseString(self, inputText, marker):
        """ Gets any string at the current position and returns it.

        Parameters
        ----------
        inputText : str
            The text being parsed
        marker : Marker
            A marker denoting the position at which to start parsing
        """

        t = ""
        quoteMarkType = ""
        foundClosingQuoteMark = False

        # Strings in .schema files can start with either single or double quote marks. Check to see if the current character is either. 
        if cut(inputText, marker.position) == "'":
            quoteMarkType = "single"
            marker.position += 1
        elif cut(inputText, marker.position) == "\"":
            quoteMarkType = "double"
            marker.position += 1
        else:
            # If the current character isn't a single or double quote mark, then there is no string, so return None.
            return None 

        # Step through the text and look for the closing quote mark.
        while marker.position < len(inputText):
            c = cut(inputText, marker.position)

            # If the closing quote mark is found, exit the loop. Otherwise, add the character to the temporary variable.
            if (quoteMarkType == "single" and c == "'") or (quoteMarkType == "double" and c == "\""):
                marker.position += 1
                foundClosingQuoteMark = True
                break
            else:
                t += c
                marker.position += 1

        # If no closing quote mark is found, then the .schema file syntax is wrong, so raise an exception.
        if not foundClosingQuoteMark:
            quoteMark = "'" if quoteMarkType == "single" else "\""
            raise SchemataParsingError(f"Expected {quoteMark} at position {marker.position}.")

        return t 

    def _parseInteger(self, inputText, marker):
        """ Gets any integer at the current position and returns it.

        Parameters
        ----------
        inputText : str
            The text being parsed
        marker : Marker
            A marker denoting the position at which to start parsing
        """

        t = ""

        # Step through the text and check if the characters are digits.
        while marker.position < len(inputText):
            c = cut(inputText, marker.position)

            if c in "0123456789":
                t += c 
                # If the current character is a digit, move the marker along by 1.
                marker.position += 1
            else:
                break 

        # If no digits are found, return None.
        if len(t) == 0:
            return None 

        return int(t)

    def _parseBoolean(self, inputText, marker):
        """ Gets any boolean at the current position and returns it.

        Parameters
        ----------
        inputText : str
            The text being parsed
        marker : Marker
            A marker denoting the position at which to start parsing
        """

        # If either 'true' or 'false' is found, return a boolean value.
        if cut(inputText, marker.position, 4) == "true":
            marker.position += 4
            return True 
        elif cut(inputText, marker.position, 5) == "false":
            marker.position += 5
            return False 

        # Otherwise return None.
        return None

    def _parseComment(self, inputText, marker):
        """ Gets any comment at the current position and returns it.

        Parameters
        ----------
        inputText : str
            The text being parsed
        marker : Marker
            A marker denoting the position at which to start parsing
        """

        # Check for the opening comment token.
        if cut(inputText, marker.position, 2) == "/*":
            marker.position += 2

            t = ""
            foundClosingTag = False 

            # Step through the text and look for the closing comment token.
            while marker.position < len(inputText):
                if cut(inputText, marker.position, 2) == "*/":
                    marker.position += 2
                    foundClosingTag = True 
                    break 
                else:
                    # Until the closing comment token is found, add any text to the temporary variable.
                    t += cut(inputText, marker.position)
                    marker.position += 1

            # If no closing comment token is found, raise an exception.
            if not foundClosingTag:
                raise SchemataParsingError(f"Expected '*/' at position {marker.position}.")

            return t
        else:
            # If no comment is found, return None.
            return None 

    def _parseWhiteSpace(self, inputText, marker):
        """ Gets any white space at the current position and returns it.

        Parameters
        ----------
        inputText : str
            The text being parsed
        marker : Marker
            A marker denoting the position at which to start parsing
        """

        t = ""

        # Step through the text and check if it is white space.
        while marker.position < len(inputText):
            c = cut(inputText, marker.position)

            if c in " \t\n":
                t += c
                # If the current character is white space, move the marker along by 1.
                marker.position += 1
            else:
                break

        # If no white space is found, return None.
        if len(t) == 0:
            return None

        return t 