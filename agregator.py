from framework.master import Master
from framework.slave import Slave
from framework.core import Core
from datetime import datetime, timedelta
import sys
# TODO REMOVE ALL NON USED IMPORTS
# TODO REPAIR CACHING AND IMPLEMENT HASH
# Download all bt_hash from master server

master = Master()
# master.clear_cache()
master.load()

# Download ureports from slave/s servers
slave = Slave()
slave.load(master_hash=master.master_bt)

# slave.print_debug()

core = Core(master=master, slave=slave)
core.run()
