import logging 
import argparse 
import glob 
from schemata.parser import *
from schemata.exporters import * 
import json 
from lxml.etree import parse, XMLSchema, XSLT, tostring


def generate():
    parser = Parser()

    fps = glob.glob("examples/*.schema")

    for fp in fps:
        logging.info("Generating an XSD file from {}.".format(fp))

        schema = parser.parseSchemaFromFile(fp)

        with open(fp[:-7] + ".json", "w") as fo:    
            json.dump(schema.toJSON(), fo , indent=4)

        exportSchemaAsXSD(schema, "vTest", fp[:-7] + ".xsd")


def validate():

    fps1 = glob.glob("examples/*.xsd")

    for fp1 in fps1:
        fp2 = fp1[:-4] + ".xml"

        xsdDocument = parse(fp1)
        schema = XMLSchema(xsdDocument)

        logging.info("Checking that all valid examples pass when validated against the XSD file.")

        fps2 = [fp2]

        for fp3 in fps2:
            xmlDocument = parse(fp3)
            isValid = schema.validate(xmlDocument)

            if isValid == True:
                logging.info(" - {} passes.".format(fp3))
            else:
                logging.info(" - {} does not pass.".format(fp3))

                schema.assertValid(xmlDocument)

        logging.info("Checking that all invalid examples fail when validated against the XSD file.")

        fps3 = []

        for fp4 in fps3:
            xmlDocument = parse(fp4)
            isValid = schema.validate(xmlDocument)

            if isValid == False:
                logging.info(" - {} fails.".format(fp4))
            else:
                logging.info(" - {} does not fail.".format(fp4))

                raise Exception("{} should fail validation, but doesn't.".format(fp4))


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    generate()
    validate()
