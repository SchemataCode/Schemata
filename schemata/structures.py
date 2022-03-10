
import logging 

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