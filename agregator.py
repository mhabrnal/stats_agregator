from framework.master import Master
from framework.slave import Slave
from framework.core import Core
import config

master = Master()
master.load()

slave = Slave()
slave.load(master_hash=master.master_bt)

core = Core(master=master,slave=slave)
core.run()





