class Core():
    master_hash = None
    slave_hash = None

    def __init__(self, master, slave):
        self.master_hash = master
        self.slave_hash = slave

    def run(self):
        print "Running"
        pass
