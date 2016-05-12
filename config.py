import os

from confire import Configuration
# from confire import environ_setting


class DDBenchConfiguration(Configuration):

    CONF_PATHS = [
        os.path.expanduser('~/.ddbench.yaml'),
        os.path.abspath('conf/ddbench.yaml')
    ]

    debug = False
    testing = True

settings = DDBenchConfiguration.load()
