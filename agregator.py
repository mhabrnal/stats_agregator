from framework.master import Master
from framework.slave import Slave
from framework.core import Core
import config
from datetime import datetime, timedelta
import sys
# TODO REMOVE ALL NON USED IMPORTS
# TODO REPAIR CACHING AND IMPLEMENT HASH
# Download all bt_hash from master server

if config.VERBOSE:
    if config.CACHE:
        print ("All results will be cached")
    else:
        print ("Cache isn't set")

if config.VERBOSE:
    print "Master processing Start"

master = Master()
# master.clear_cache()
master.load()

if config.VERBOSE:
    print "Master processing stop"
    print "To slave was sended {0} bt hash from master".format(len(
        master.master_bt))


# Download ureports from slave/s servers
slave = Slave()
slave.load(master_hash=master.master_bt)


if config.VERBOSE:
    print "Slave processing stop"

core = Core(master=master, slave=slave)
core.run()
