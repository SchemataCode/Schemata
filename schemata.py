import os 
import logging 
import re
from lxml.etree import ElementTree as XMLElementTree, Element as XMLElement, SubElement as XMLSubelement, Comment as XMLComment, QName, indent 
import json 

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class Schema(object):
    def __init__(self):
        self.formatName = ""
        self.structures = []
        self.dependencies = []

    @property 
    def _allStructures(self):
        return [structure for dependency in self.dependencies for structure in dependency.structures] + self.structures 

    def getStructureByReference(self, reference):
        d = {structure.reference : structure for structure in self._allStructures}

        return d.get(reference, None)

    def getDataStructures(self):
        return [structure for structure in self._allStructures if isinstance(structure, DataStructure)]

    def getAttributeStructures(self):
        return [structure for structure in self._allStructures if isinstance(structure, AttributeStructure)]

    def getElementStructures(self):
        return [structure for structure in self._allStructures if isinstance(structure, ElementStructure)]

    def getRootElementStructures(self):
        return [structure for structure in self.getElementStructures() if structure.canBeRootElement]

    def getNonRootElementStructures(self):
        return [structure for structure in self.getElementStructures() if not structure.canBeRootElement]

    def getObjectStructures(self):
        return [structure for structure in self._allStructures if isinstance(structure, ObjectStructure)]

    def getRootObjectStructures(self):
        return [structure for structure in self.getObjectStructures() if structure.canBeRootObject]

    def setIsUsed(self):
        rootElementStructures = self.getRootElementStructures()

        for rootElementStructure in rootElementStructures:
            rootElementStructure.setIsUsed()

    def toJSON(self):
        return {
            "formatName": self.formatName,
            "structures": [structure.toJSON() if hasattr(structure, "toJSON") else structure for structure in self.structures]
        }


class StructureMetadata(object):
    def __init__(self):
        self.description = ""
        self.exampleValue = ""

    def toJSON(self):
        return {
            "description": self.description,
            "exampleValue": self.exampleValue
        }


class Structure(object):
    def __init__(self, reference = ""):
        self.schema = None 

        self.baseStructureReference = ""

        self.reference = reference
        self.isUsed = False 

        self.metadata = StructureMetadata()

    @property 
    def baseStructure(self):
        return self.schema.getStructureByReference(self.baseStructureReference)

    def setIsUsed(self):
        self.isUsed = True 

        if self.baseStructure != None:
            self.baseStructure.setIsUsed()

    def toJSON(self):
        return {}


class DataStructure(Structure):
    def __init__(self, reference = ""):
        super().__init__(reference)

        self.allowedPattern = ""
        self.allowedValues = []

        self.minimumValue = None 
        self.maximumValue = None 

        self.defaultValue = None 

    def toJSON(self):
        return {
            "type":"DataStructure",
            "baseStructureReference": self.baseStructureReference,
            "reference": self.reference,
            "isUsed": self.isUsed,
            "metadata": self.metadata.toJSON(),
            "allowedPattern": self.allowedPattern,
            "allowedValues": self.allowedValues,
            "minimumValue": self.minimumValue,
            "maximumValue": self.maximumValue,
            "defaultValue": self.defaultValue
        }


class ListFunction(object):
    def __init__(self, dataStructureReference, separator):
        self.schema = None 

        self.dataStructureReference = dataStructureReference 
        self.separator = separator 

    @property 
    def dataStructure(self):
        return self.schema.getStructureByReference(self.dataStructureReference)

    def setIsUsed(self):
        if self.dataStructure != None:
            self.dataStructure.setIsUsed()


class AttributeStructure(Structure):
    def __init__(self, reference = ""):
        super().__init__(reference)

        self.attributeName = ""
        self.dataStructureReference = ""
        self.defaultValue = None 

    @property 
    def dataStructure(self):
        return self.schema.getStructureByReference(self.dataStructureReference)

    def setIsUsed(self):
        super().setIsUsed()

        if self.dataStructure != None:
            self.dataStructure.setIsUsed()

    def toJSON(self):
        return {
            "type":"AttributeStructure",
            "baseStructureReference": self.baseStructureReference,
            "reference": self.reference,
            "isUsed": self.isUsed,
            "metadata": self.metadata.toJSON(),
            "attributeName": self.attributeName,
            "dataStructureReference": self.dataStructureReference,
            "defaultValue": self.defaultValue 
        }


class ElementStructure(Structure):
    def __init__(self, reference = ""):
        super().__init__(reference)

        self.elementName = ""
        self.canBeRootElement = False 
        self.attributes = []
        self.allowedContent = None 
        self.valueTypeReference = ""

        self.isSelfClosing = False 
        self.lineBreaks = [0, 1, 1, 1]

    @property 
    def hasAttributes(self):
        return len(self.attributes) > 0

    @property 
    def hasContent(self):
        if self.allowedContent == None:
            return False 

        if isinstance(self.allowedContent, StructureList) and len(self.allowedContent.structures) == 0:
            return False 

        return True 

    @property 
    def containsElementUsageReference(self):
        if isinstance(self.allowedContent, ElementUsageReference):
            return True 

        if isinstance(self.allowedContent, AnyElementsUsageReference):
            return True

        if isinstance(self.allowedContent, StructureList):
            # To do: this needs to be recursive.
            if len([structure for structure in self.allowedContent.structures if isinstance(structure, ElementUsageReference) or isinstance(structure, AnyElementsUsageReference) or isinstance(structure, StructureList)]) > 0:
                return True 

        return False 

    @property 
    def containsAnyTextUsageReference(self):
        if isinstance(self.allowedContent, AnyTextUsageReference):
            return True 

        if isinstance(self.allowedContent, StructureList):
            if len([structure for structure in self.allowedContent.structures if isinstance(structure, AnyTextUsageReference)]) > 0:
                return True 

        return False 

    @property 
    def contentIsAnyText(self):
        return self.containsAnyTextUsageReference and not self.containsElementUsageReference 

    @property 
    def contentIsSingleValue(self):
        return isinstance(self.allowedContent, DataUsageReference)

    @property 
    def contentIsElementsOnly(self):
        return self.containsElementUsageReference and not self.containsAnyTextUsageReference 

    @property 
    def contentIsElementsAndAnyText(self):
        return self.containsElementUsageReference and self.containsAnyTextUsageReference

    @property 
    def valueType(self):
        return self.schema.getStructureByReference(self.valueTypeReference)

    def setIsUsed(self):
        super().setIsUsed()

        for attributeUsageReference in self.attributes:
            logger.info(f"Setting isUsed for {self.reference}.{attributeUsageReference.attributeStructureReference}.")

            attributeUsageReference.attributeStructure.setIsUsed()

        if self.allowedContent != None:
            self.allowedContent.setIsUsed()

    def toJSON(self):
        return {
            "type":"ElementStructure",
            "baseStructureReference": self.baseStructureReference,
            "reference": self.reference,
            "isUsed": self.isUsed,
            "metadata": self.metadata.toJSON(),
            "elementName": self.elementName,
            "canBeRootElement": self.canBeRootElement,
            "attributes": [a.toJSON() for a in self.attributes],
            "allowedContent": None if self.allowedContent == None else self.allowedContent.toJSON(),
            "isSelfClosing": self.isSelfClosing,
            "lineBreaks": self.lineBreaks
        }


class PropertyStructure(Structure):
    def __init__(self, reference = ""):
        super().__init__(reference)

        self.propertyName = ""
        self.valueTypeReference = ""

    @property 
    def valueType(self):
        return self.schema.getStructureByReference(self.valueTypeReference)

    def setIsUsed(self):
        super().setIsUsed()

        if self.valueType != None:
            self.valueType.setIsUsed()

    def toJSON(self):
        return {
            "type":"PropertyStructure",
            "baseStructureReference": self.baseStructureReference,
            "reference": self.reference,
            "isUsed": self.isUsed,
            "metadata": self.metadata.toJSON(),
            "valueTypeReference": self.valueTypeReference 
        }


class ArrayStructure(Structure):
    def __init__(self, reference = ""):
        super().__init__(reference)

        self.itemTypeReference = ""

    @property 
    def itemType(self):
        return self.schema.getStructureByReference(self.itemTypeReference)

    def setIsUsed(self):
        super().setIsUsed()

        if self.itemType != None:
            self.itemType.setIsUsed()

    def toJSON(self):
        return {
            "type":"ArrayStructure",
            "baseStructureReference": self.baseStructureReference,
            "reference": self.reference,
            "isUsed": self.isUsed ,
            "metadata": self.metadata.toJSON(),
            "itemTypeReference": self.itemTypeReference 
        }


class ObjectStructure(Structure):
    def __init__(self, reference = ""):
        super().__init__(reference)

        self.canBeRootObject = False 
        self.properties = []

    def setIsUsed(self):
        super().setIsUsed()

        for propertyUsageReference in self.properties:
            propertyUsageReference.propertyStructure.setIsUsed()

    def toJSON(self):
        return {
            "type":"ObjectStructure",
            "baseStructureReference": self.baseStructureReference,
            "reference": self.reference,
            "isUsed": self.isUsed,
            "metadata": self.metadata.toJSON(),
            "canBeRootObject": self.canBeRootObject,
            "properties": [p.toJSON() for p in self.properties]
        }


class UsageReference(object):
    def __init__(self):
        self.schema = None 

    def setIsUsed(self):
        pass

    def toJSON(self):
        return {}


class DataUsageReference(UsageReference):
    def __init__(self):
        super().__init__()

        self.dataStructureReference = ""

    @property 
    def dataStructure(self):
        return self.schema.getStructureByReference(self.dataStructureReference)

    def setIsUsed(self):
        if self.dataStructure != None:
            self.dataStructure.setIsUsed()

    def toJSON(self):
        return {
            "dataStructureReference": self.dataStructureReference
        }


class AttributeUsageReference(UsageReference):
    def __init__(self):
        super().__init__()

        self.attributeStructureReference = ""
        self.isOptional = False 
        self.defaultValue = None 

    @property 
    def attributeStructure(self):
        return self.schema.getStructureByReference(self.attributeStructureReference)

    def setIsUsed(self):
        if self.attributeStructure != None:
            self.attributeStructure.setIsUsed()

    def toJSON(self):
        return {
            "attributeStructureReference": self.attributeStructureReference,
            "isOptional": self.isOptional,
            "defaultValue": self.defaultValue
        }


class ElementUsageReference(UsageReference):
    def __init__(self):
        super().__init__()

        self.elementStructureReference= ""
        self.nExpression = None 
        self.minimumNumberOfOccurrences = 1
        self.maximumNumberOfOccurrences = 1

    @property 
    def elementStructure(self):
        return self.schema.getStructureByReference(self.elementStructureReference)

    def setIsUsed(self):
        if self.elementStructure != None:
            self.elementStructure.setIsUsed()

    def toJSON(self):
        return {
            "elementStructureReference": self.elementStructureReference,
            "minimumNumberOfOccurrences": self.minimumNumberOfOccurrences,
            "maximumNumberOfOccurrences":self.maximumNumberOfOccurrences
        }


class PropertyUsageReference(UsageReference):
    def __init__(self):
        super().__init__()

        self.propertyStructureReference = ""
        self.isOptional = False 
        self.defaultValue = None 

    @property 
    def propertyStructure(self):
        return self.schema.getStructureByReference(self.propertyStructureReference)

    def setIsUsed(self):
        if self.propertyStructure != None:
            self.propertyStructure.setIsUsed()

    def toJSON(self):
        return {
            "propertyStructureReference": self.propertyStructureReference,
            "isOptional": self.isOptional,
            "defaultValue": self.defaultValue
        }


class AnyAttributesUsageReference(UsageReference):
    pass 


class AnyElementsUsageReference(UsageReference):
    pass 


class AnyTextUsageReference(UsageReference):
    pass 


class AnyPropertiesUsageReference(UsageReference):
    pass 


class StructureList(object):
    def __init__(self):
        self.schema = None 

        self.structures = [] 

    @property 
    def containsText(self):
        for structureUsageReference in self.structures:
            if isinstance(structureUsageReference, AnyTextUsageReference):
                return True 
            
            if isinstance(structureUsageReference, UnorderedStructureList):
                containsText = structureUsageReference.containsText()

                if containsText == True:
                    return True 

            if isinstance(structureUsageReference, OrderedStructureList):
                containsText = structureUsageReference.containsText()

                if containsText == True:
                    return True 

            if isinstance(structureUsageReference, StructureChoice):
                containsText = structureUsageReference.containsText()

                if containsText == True:
                    return True 

    def setIsUsed(self):
        for structureUsageReference in self.structures:
            structureUsageReference.setIsUsed()

    def toJSON(self):
        return {}


class UnorderedStructureList(StructureList):

    def toJSON(self):
        return {
            "type": "UnorderedStructureList",
            "structures": [structure.toJSON() for structure in self.structures]
        }


class OrderedStructureList(StructureList):

    def toJSON(self):
        return {
            "type": "OrderedStructureList",
            "structures": [structure.toJSON() for structure in self.structures]
        }


class StructureChoice(StructureList):

    def toJSON(self):
        return {
            "type": "StructureChoice",
            "structures": [structure.toJSON() for structure in self.structures]
        }


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

