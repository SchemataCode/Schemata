import logging 
import schemata 
import glob 
import argparse 
from lxml.etree import parse, XMLSchema 
import json 


def generate():
    parser = schemata.Parser()

    fps = glob.glob("schemata_test_files/*.schema")

    for fp in fps:
        logging.info("Generating an XSD file from {}.".format(fp))

        schema = parser.parseSchemaFromFile(fp)

        with open(fp[:-7] + ".json", "w") as fo:    
            json.dump(schema.toJSON(), fo , indent=4)

        schemata.exportSchemaAsXSD(schema, "vTest", fp[:-7] + ".xsd")


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    generate()
