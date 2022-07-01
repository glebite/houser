"""manager.py
"""
import configparser
import argparse
import logging
import sys


class Manager:
    """
    """
    def __init__(self, config_file):
        self.config_file = config_file
        self.configuration = None

    def configure(self):
        self.configuration = configparser.ConfigParser()
        try:
            self.configuration.read(self.config_file)
        except (configparser.Error, IOError, OSError) as err:
            print(err)
            sys.exit(1)

def main(configuration_file):
    """
    """
    pass


if __name__=="__main__":
    parser = argparse.ArgumentParser(description = 'House Manager Reporter System.')
    parser.add_argument('config', help='path to the configuration file')
    args = parser.parse_args()
    main(args.config)
