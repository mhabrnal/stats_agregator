from framework.master import Master
from framework.slave import Slave
from framework.core import Core
import config
from datetime import datetime, timedelta
import sys
# TODO REMOVE ALL NON USED IMPORTS
# TODO REPAIR CACHING AND IMPLEMENT HASH
# TODO REMOVE VERBOSE
# Download all bt_hash from master server

if config.VERBOSE:
    if config.CACHE:
        print ("All results will be cached")
    else:
        print ("Cache isn't set")

core = Core()
core.run()
