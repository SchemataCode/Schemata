import logging 

logger = logging.getLogger("schemata.structures")

"""
This module contains the core classes for Schemata.

There are, broadly, three categories of class here.

The first is the Schema class, which simply represents the entire schema. It contains all of the structures.

The second is structure classes. A Schemata document consists of a set of different kinds of structures.
A structure might define an XML element, or an XML attribute, or a JSON object, and so on.

The third is usage references. A usage reference defines how one structure uses another structure. For example,
an element structure might want to refer to a number of attribute structures that it uses. However, these
attribute structures might be optional in this context, or have different default values to usual. This is what
the usage reference defines.
"""


class Schema(object):
    """
    Represents a schema.

    ...

    Attributes
    ----------
    formatName : str
        the name of this XML or JSON format
    structures : list
        the structures in this format
    dependencies : list
        the schemas on which this schema depends, if any
    
    """

    def __init__(self):
        self.formatName = ""
        self.structures = []
        self.dependencies = []

    @property 
    def _allStructures(self):
        return [structure for dependency in self.dependencies for structure in dependency.structures] + self.structures 

    def getStructureByReference(self, reference):
        """
        Gets the structure with the given reference.

        Parameters
        ----------
        reference : str
            the reference of the structure to get

        Returns
        -------
        Either the structure with the given reference, or None if none is found.
        
        """

        d = {structure.reference : structure for structure in self._allStructures}

        return d.get(reference, None)

    def getDataStructures(self):
        """
        Gets all of the data structures in this schema.

        Returns
        -------
        A list of data structures.
        """

        return [structure for structure in self._allStructures if isinstance(structure, DataStructure)]

    def getAttributeStructures(self):
        """
        Gets all of the XML attribute structures in this schema.

        Returns
        -------
        A list of attribute structures.
        """

        return [structure for structure in self._allStructures if isinstance(structure, AttributeStructure)]

    def getElementStructures(self):
        """
        Gets all of the XML element structures in this schema.

        Returns
        -------
        A list of element structures.
        """

        return [structure for structure in self._allStructures if isinstance(structure, ElementStructure)]

    def getRootElementStructures(self):
        """
        Gets all of the XML root element structures in this schema.

        Returns
        -------
        A list of element structures.
        """

        return [structure for structure in self.getElementStructures() if structure.canBeRootElement]

    def getNonRootElementStructures(self):
        """
        Gets all of the XML non-root element structures in this schema.

        Returns
        -------
        A list of element structures.
        """

        return [structure for structure in self.getElementStructures() if not structure.canBeRootElement]

    def getObjectStructures(self):
        """
        Gets all of the JSON object structures in this schema.

        Returns
        -------
        A list of object structures.
        """

        return [structure for structure in self._allStructures if isinstance(structure, ObjectStructure)]

    def getRootObjectStructures(self):
        """
        Gets all of the JSON root object structures in this schema.

        Returns
        -------
        A list of object structures.
        """

        return [structure for structure in self.getObjectStructures() if structure.canBeRootObject]

    def setIsUsed(self):
        """
        Sets the isUsed property for every structure in the schema. This property determines whether or not a structure 
        will appear in the exported schema format, so this function must be called by the exporter at some point.

        Returns
        -------
        None
        """

        rootElementStructures = self.getRootElementStructures()

        for rootElementStructure in rootElementStructures:
            rootElementStructure.setIsUsed()

    def toJSON(self):
        """
        Converts this object to a dictionary, which can then be easily exported as JSON. Used for development purposes.

        Returns
        -------
        A dictionary representing this object.
        """

        return {
            "formatName": self.formatName,
            "structures": [structure.toJSON() if hasattr(structure, "toJSON") else structure for structure in self.structures]
        }


class StructureMetadata(object):
    """
    Captures the metadata for a structure. The metadata is used in automatic documentation generation.

    ...

    Attributes
    ----------
    description : str
        a description of this structure
    exampleValue : str
        an example value for this structure, if relevant

    """

    def __init__(self):
        self.description = ""
        self.exampleValue = ""

    def toJSON(self):
        """
        Converts this object to a dictionary, which can then be easily exported as JSON. Used for development purposes.

        Returns
        -------
        A dictionary representing this object.
        """

        return {
            "description": self.description,
            "exampleValue": self.exampleValue
        }


class Structure(object):
    """
    A base class for all structures. Defines common properties.

    ...

    Attributes
    ----------
    schema : Schema
        the schema that this structure is in
    baseStructureReference : string
        the reference of the base structure of this structure
    baseStructure : Structure
        the base structure of this structure
    reference : string
        the reference of this structure
    isUsed : boolean
        whether or not this structure is used in the schema
    metadata : StructureMetadata
        the metadata for this structure 
    """
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
        """
        Sets the isUsed property for this structure and the structures it depends on.

        Returns
        -------
        None 
        """

        self.isUsed = True 

        if self.baseStructure != None:
            self.baseStructure.setIsUsed()

    def toJSON(self):
        """
        Converts this object to a dictionary, which can then be easily exported as JSON. Used for development purposes.

        Returns
        -------
        A dictionary representing this object.
        """

        return {}


class DataStructure(Structure):
    """
    A class for data structures.

    ...

    Attributes
    ----------
    allowedPattern : string
        a regular expression describing what patterns this data structure can have (if the base type is a string)
    allowedValues : list
        a list of the different values that this data structure can have (effectively defining an enumeration); can be a list of strings or numbers
    minimumValue : number
        the minimum value (inclusive) that this data structure can have (if the base type is an integer or a decimal)
    maximumValue : number
        the maximum value (inclusive) that this data structure can have (if the base type is an integer or a decimal)
    defaultValue : any
        the default value that this data structure takes
    """

    def __init__(self, reference = ""):
        super().__init__(reference)

        self.allowedPattern = ""
        self.allowedValues = []

        self.minimumValue = None 
        self.maximumValue = None 

        self.defaultValue = None 

    def toJSON(self):
        """
        Converts this object to a dictionary, which can then be easily exported as JSON. Used for development purposes.

        Returns
        -------
        A dictionary representing this object.
        """

        return {
            "type": "DataStructure",
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
    """
    A class that represents a kind of 'meta-data-structure'. If a list function is used in a Schemata file, it means that a data type should be used that is a 
    list of another data type. Adding list-like data types manually is tedious, as it often involves writing a very complex regular expression - list functions
    do this automatically in Schemata.

    ...

    Attributes
    ----------
    schema : Schema
        the schema that this list function is in
    dataStructureReference : string
        the reference of the data structure that this list function should be a list of
    dataStructure : DataStructure
        the data structure that this list function should be a list of 
    separator : string
        the character or set of characters that should act as separators in this list - usually a comma or a semi-colon
    """

    def __init__(self, dataStructureReference, separator):
        self.schema = None 

        self.dataStructureReference = dataStructureReference 
        self.separator = separator 

    @property 
    def dataStructure(self):
        return self.schema.getStructureByReference(self.dataStructureReference)

    def setIsUsed(self):
        """
        Sets the isUsed property for the structure this list function depends on.

        Returns
        -------
        None 
        """

        if self.dataStructure != None:
            self.dataStructure.setIsUsed()


class AttributeStructure(Structure):
    """
    A class for XML attribute structures.

    ...

    Attributes
    ----------
    attributeName : string
        the name of this XML attribute
    dataStructureReference : string
        the reference of the data structure that should be used as the value of this attribute
    dataStructure : DataStructure
        the data structure that should be used as the value of this attribute
    defaultValue : any
        the default value of this attribute; overrides the default value set by the data structure
    """

    def __init__(self, reference = ""):
        super().__init__(reference)

        self.attributeName = ""
        self.dataStructureReference = ""
        self.defaultValue = None 

    @property 
    def dataStructure(self):
        return self.schema.getStructureByReference(self.dataStructureReference)

    def setIsUsed(self):
        """
        Sets the isUsed property for this structure and the structures it depends on.

        Returns
        -------
        None 
        """

        super().setIsUsed()

        if self.dataStructure != None:
            self.dataStructure.setIsUsed()

    def toJSON(self):
        """
        Converts this object to a dictionary, which can then be easily exported as JSON. Used for development purposes.

        Returns
        -------
        A dictionary representing this object.
        """

        return {
            "type": "AttributeStructure",
            "baseStructureReference": self.baseStructureReference,
            "reference": self.reference,
            "isUsed": self.isUsed,
            "metadata": self.metadata.toJSON(),
            "attributeName": self.attributeName,
            "dataStructureReference": self.dataStructureReference,
            "defaultValue": self.defaultValue 
        }


class ElementStructure(Structure):
    """
    A class for XML element structures.

    ...

    Attributes
    ----------
    elementName : string
        the tag name of this element
    canBeRootElement : boolean
        whether or not this element can be the root element of the XML document
    attributes : list
        a list of attribute usage references that specify what attributes this element can have
    allowedContent : a type of UsageReference or StructureList
        a hierarchical collection of objects defining what elements and data this element can contain
    valueTypeReference : a string
        if the content of this element is simply a value - i.e., a data structure - then this is the reference to that data structure
    valueType : DataStructure
        if the content of this element is simply a value - i.e., a data structure - then this is that data structure
    isSelfClosing : boolean
        whether or not this element should be self-closing; XSD is indifferent to whether elements are self-closing or not; this value
        is mainly used in the auto-generation of documentation
    lineBreaks : list of integers
        how many line breaks there should be before the opening tag, after the opening tag, before the closing tag, and after the closing tag;
        XSD is indifferent to the formatting of a given XML file; this value is mainly used in the auto-generation of documentation, and could
        also be used by IDE extensions for auto-formatting
    hasAttributes : boolean
        whether or not this element has any allowed attributes; mainly used by the Schemata exporter
    hasContent : boolean
        whether or not this element has any allowed content; mainly used by the Schemata exporter
    containsElementUsageReference : boolean
        whether or not this element structure contains and element usage references; in short, whether 
        or not this element can contain other elements; mainly used by the Schemata exporter
    containsAnyTextUsageReference : boolean
        whether or not this element structure contains an 'any text' usage reference; in short, whether
        or not this element can contain any text (rather than a specific text string defined by a data
        structure); mainly used by the Schemata exporter
    contentIsAnyText : boolean
        whether or not this element can contain any text, but no elements; mainly used by the Schemata exporter
    contentIsSingleValue : boolean
        whether or not this element is a single value defined by a data structure; mainly used by the Schemata exporter
    contentIsElementsOnly : boolean
        whether or not this element can only contain other elements, and no text; mainly used by the Schemata exporter
    contentIsElementsAndAnyText : boolean
        whether or not this element is a mixed type - i.e., it can contain a mixture of subelements and 
        any text; common in HTML-like documents; mainly used by the Schemata exporter
    """
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
        """
        Sets the isUsed property for this structure and the structures it depends on.

        Returns
        -------
        None 
        """

        super().setIsUsed()

        for attributeUsageReference in self.attributes:
            logger.info(f"Setting isUsed for {self.reference}.{attributeUsageReference.attributeStructureReference}.")

            attributeUsageReference.attributeStructure.setIsUsed()

        if self.allowedContent != None:
            self.allowedContent.setIsUsed()

    def toJSON(self):
        """
        Converts this object to a dictionary, which can then be easily exported as JSON. Used for development purposes.

        Returns
        -------
        A dictionary representing this object.
        """

        return {
            "type": "ElementStructure",
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
    """
    A class for JSON property structures.

    ...

    Attributes
    ----------
    propertyName : string
        the name of this JSON property
    valueTypeReference : string
        the reference of the structure that the value of this property should be
    valueType : Structure
        the structure that the value of this property should be; can be a data structure, an array structure, or an object structure
    """

    def __init__(self, reference = ""):
        super().__init__(reference)

        self.propertyName = ""
        self.valueTypeReference = ""

    @property 
    def valueType(self):
        return self.schema.getStructureByReference(self.valueTypeReference)

    def setIsUsed(self):
        """
        Sets the isUsed property for this structure and the structures it depends on.

        Returns
        -------
        None 
        """

        super().setIsUsed()

        if self.valueType != None:
            self.valueType.setIsUsed()

    def toJSON(self):
        """
        Converts this object to a dictionary, which can then be easily exported as JSON. Used for development purposes.

        Returns
        -------
        A dictionary representing this object.
        """

        return {
            "type": "PropertyStructure",
            "baseStructureReference": self.baseStructureReference,
            "reference": self.reference,
            "isUsed": self.isUsed,
            "metadata": self.metadata.toJSON(),
            "valueTypeReference": self.valueTypeReference 
        }


class ArrayStructure(Structure):
    """
    A class for JSON array structures.

    ...

    Attributes
    ----------
    itemTypeReference : string
        the reference to the structure that all of the items of this array conform to
    itemType : Structure
        the structure that all of the items of this array conform to; can be a data structure, an array structure, or an object structure
    """
    def __init__(self, reference = ""):
        super().__init__(reference)

        self.itemTypeReference = ""

    @property 
    def itemType(self):
        return self.schema.getStructureByReference(self.itemTypeReference)

    def setIsUsed(self):
        """
        Sets the isUsed property for this structure and the structures it depends on.

        Returns
        -------
        None 
        """

        super().setIsUsed()

        if self.itemType != None:
            self.itemType.setIsUsed()

    def toJSON(self):
        """
        Converts this object to a dictionary, which can then be easily exported as JSON. Used for development purposes.

        Returns
        -------
        A dictionary representing this object.
        """

        return {
            "type": "ArrayStructure",
            "baseStructureReference": self.baseStructureReference,
            "reference": self.reference,
            "isUsed": self.isUsed ,
            "metadata": self.metadata.toJSON(),
            "itemTypeReference": self.itemTypeReference 
        }


class ObjectStructure(Structure):
    """
    A class for JSON object structures.

    ...

    Attributes
    ----------
    canBeRootObject : boolean
        whether or not this object structure can be the root object of the JSON document
    properties : list
        a list of property usage references that defines the properties this object can have
    
    """
    def __init__(self, reference = ""):
        super().__init__(reference)

        self.canBeRootObject = False 
        self.properties = []

    def setIsUsed(self):
        """
        Sets the isUsed property for this structure and the structures it depends on.

        Returns
        -------
        None 
        """

        super().setIsUsed()

        for propertyUsageReference in self.properties:
            propertyUsageReference.propertyStructure.setIsUsed()

    def toJSON(self):
        """
        Converts this object to a dictionary, which can then be easily exported as JSON. Used for development purposes.

        Returns
        -------
        A dictionary representing this object.
        """

        return {
            "type": "ObjectStructure",
            "baseStructureReference": self.baseStructureReference,
            "reference": self.reference,
            "isUsed": self.isUsed,
            "metadata": self.metadata.toJSON(),
            "canBeRootObject": self.canBeRootObject,
            "properties": [p.toJSON() for p in self.properties]
        }


class UsageReference(object):
    """
    A usage reference base class. While structures *define* things like elements or objects, usage references are statements of how and where they are used.
    A usage reference includes things like whether an attribute is optional, or how many times a subelement should be repeated.

    ...

    Attributes
    ----------
    schema : Schema
        the schema that this usage reference is used in.
    """
    def __init__(self):
        self.schema = None 

    def setIsUsed(self):
        pass

    def toJSON(self):
        return {}


class DataUsageReference(UsageReference):
    """
    A class for a data structure usage reference.

    ...

    Attributes
    ----------
    dataStructureReference : string
        the reference of the data structure that this usage reference pertains to
    dataStructure : DataStructure
        the data structure that this usage reference pertains to
    """
    def __init__(self):
        super().__init__()

        self.dataStructureReference = ""

    @property 
    def dataStructure(self):
        return self.schema.getStructureByReference(self.dataStructureReference)

    def setIsUsed(self):
        """
        Sets the isUsed property for the structures this usage reference depends on.

        Returns
        -------
        None 
        """

        if self.dataStructure != None:
            self.dataStructure.setIsUsed()

    def toJSON(self):
        """
        Converts this object to a dictionary, which can then be easily exported as JSON. Used for development purposes.

        Returns
        -------
        A dictionary representing this object.
        """

        return {
            "dataStructureReference": self.dataStructureReference
        }


class AttributeUsageReference(UsageReference):
    """
    A class for an attribute structure usage reference.

    ...

    Attributes
    ----------
    attributeStructureReference : string
        the reference of the attribute structure this usage reference pertains to
    attributeStructure : AttributeStructure
        the attribute structure this usage reference pertains to
    isOptional : boolean
        whether or not this attribute is optional in this context
    defaultValue : any
        the default value of this attribute in this context; overrides the default value set by the attribute structure and the default value set by the value data structure
    """

    def __init__(self):
        super().__init__()

        self.attributeStructureReference = ""
        self.isOptional = False 
        self.defaultValue = None 

    @property 
    def attributeStructure(self):
        return self.schema.getStructureByReference(self.attributeStructureReference)

    def setIsUsed(self):
        """
        Sets the isUsed property for the structures this usage reference depends on.

        Returns
        -------
        None 
        """

        if self.attributeStructure != None:
            self.attributeStructure.setIsUsed()

    def toJSON(self):
        """
        Converts this object to a dictionary, which can then be easily exported as JSON. Used for development purposes.

        Returns
        -------
        A dictionary representing this object.
        """

        return {
            "attributeStructureReference": self.attributeStructureReference,
            "isOptional": self.isOptional,
            "defaultValue": self.defaultValue
        }


class ElementUsageReference(UsageReference):
    """
    A class for an element structure usage reference.

    ...

    Attributes
    ----------
    elementStructureReference : string
        the reference of the element structure that this usage reference pertains to
    elementStructure : ElementStructure
        the element structure that this usage reference pertains to
    nExpression : array of tuples
        an array of tuples defining the limits of how many repeats of this element there should be
    minimumNumberOfOccurrences : integer
        the minimum number of occurrences (inclusive) that there must be of this element
    maximumNumberOfOccurrences : integer
        the maximum number of occurrences (inclusive) that there must be of this element
    """
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
        """
        Sets the isUsed property for the structures this usage reference depends on.

        Returns
        -------
        None 
        """

        if self.elementStructure != None:
            self.elementStructure.setIsUsed()

    def toJSON(self):
        """
        Converts this object to a dictionary, which can then be easily exported as JSON. Used for development purposes.

        Returns
        -------
        A dictionary representing this object.
        """

        return {
            "elementStructureReference": self.elementStructureReference,
            "minimumNumberOfOccurrences": self.minimumNumberOfOccurrences,
            "maximumNumberOfOccurrences": self.maximumNumberOfOccurrences
        }


class PropertyUsageReference(UsageReference):
    """
    A class for a property structure usage reference.

    ...

    Attributes
    ----------
    propertyStructureReference : string
        the reference of the property structure that this usage reference pertains to
    propertyStructure : PropertyStructure
        the property structure that this usage reference pertains to
    isOptional : boolean
        whether this property is optional in this context
    defaultValue : any
        the default value of this property in this context
    """

    def __init__(self):
        super().__init__()

        self.propertyStructureReference = ""
        self.isOptional = False 
        self.defaultValue = None 

    @property 
    def propertyStructure(self):
        return self.schema.getStructureByReference(self.propertyStructureReference)

    def setIsUsed(self):
        """
        Sets the isUsed property for the structures this usage reference depends on.

        Returns
        -------
        None 
        """

        if self.propertyStructure != None:
            self.propertyStructure.setIsUsed()

    def toJSON(self):
        """
        Converts this object to a dictionary, which can then be easily exported as JSON. Used for development purposes.

        Returns
        -------
        A dictionary representing this object.
        """

        return {
            "propertyStructureReference": self.propertyStructureReference,
            "isOptional": self.isOptional,
            "defaultValue": self.defaultValue
        }


class AnyAttributesUsageReference(UsageReference):
    """
    A class for a wildcard usage reference that indicates that any attributes can be attached to an element.
    """
    pass 


class AnyElementsUsageReference(UsageReference):
    """
    A class for a wildcard usage reference that indicates that any element can be a subelement of an element.
    """
    pass 


class AnyTextUsageReference(UsageReference):
    """
    A class for a wildcard usage reference that indicates any text can be contained within an element.
    """
    pass 


class AnyPropertiesUsageReference(UsageReference):
    """
    A class for a wildcard usage reference that indicates that any properties can be attached to an object.
    """
    pass 


class StructureList(object):
    """
    Represents a list of structures usage references. This is used in the allowedContent property of the ElementStructure class.

    This is the base class. Derived classes specify whether the structures must appear in order, or whether the list represents a choice between structures.

    ...

    Attributes
    ----------
    schema : Schema
        the schema that this structure list is in
    structures : list
        the structure usage references in this list
    containsText : boolean
        whether this structure list contains an AnyTextUsageReference, at any level of depth
    """

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
        """
        Sets the isUsed property for the structures this list depends on.

        Returns
        -------
        None 
        """

        for structureUsageReference in self.structures:
            structureUsageReference.setIsUsed()

    def toJSON(self):
        return {}


class UnorderedStructureList(StructureList):
    """
    Represents a type of structure list where the order is not important.
    """

    def toJSON(self):
        """
        Converts this object to a dictionary, which can then be easily exported as JSON. Used for development purposes.

        Returns
        -------
        A dictionary representing this object.
        """

        return {
            "type": "UnorderedStructureList",
            "structures": [structure.toJSON() for structure in self.structures]
        }


class OrderedStructureList(StructureList):
    """
    Represents a type of structure list where the order is important.
    """

    def toJSON(self):
        """
        Converts this object to a dictionary, which can then be easily exported as JSON. Used for development purposes.

        Returns
        -------
        A dictionary representing this object.
        """

        return {
            "type": "OrderedStructureList",
            "structures": [structure.toJSON() for structure in self.structures]
        }


class StructureChoice(StructureList):
    """
    Represents a type of structure list where only one of the structures can be used.
    """

    def toJSON(self):
        """
        Converts this object to a dictionary, which can then be easily exported as JSON. Used for development purposes.

        Returns
        -------
        A dictionary representing this object.
        """

        return {
            "type": "StructureChoice",
            "structures": [structure.toJSON() for structure in self.structures]
        }