import ast
import sys
from pprint import pprint

class Core:

    master_hash = None
    slave_hash = None
    slave_dict = dict()

    # Data for separate steps
    step1 = dict()  # Bugzilla bugs with closed Fedora Bugzilla bugs

    def __init__(self, master, slave):
        self.master_hash = master
        self.slave_hash = slave

    def run(self):
        print "Start working with data"

        self.agregate_master_bthash()
        self.master_hash.download_ureport()  # Download ureports
        self.group_data_by_bt_hash()
        self.summarize_data()
        self.generate_output()



        print "All is done"
        sys.exit()

    def generate_output(self):
        self.master_hash.download_ureport()
        for key_hash in self.slave_dict.keys():
            if key_hash in self.master_hash.master_bt:
                print "TEST", key_hash

    def agregate_master_bthash(self):
        """
        Aggregate all unique bt_hash from slave servers and assign to
        master variable for downloading ureports from master
        """
        correct_bthashes = []
        for hashes in self.slave_hash.slave_bt.values():
            for slave_bthash in hashes.keys():
                if slave_bthash not in correct_bthashes:
                    correct_bthashes.append(slave_bthash)
        self.master_hash.master_bt = correct_bthashes

    def group_data_by_bt_hash(self):
        for master_bt, master_ureport in self.master_hash.master_bt.items():
            for server_name, slave_report in self.slave_hash.slave_bt.items():
                if master_bt in slave_report:
                    tmp_ureport = slave_report[master_bt]
                    #  tmp_ureport['source'] = server_name  # TODO Replace with
                    #  TODO url or delete tmp_ureport variable
                    self.slave_dict[master_bt] = tmp_ureport

    def summarize_data(self):
        for bthash, value in self.slave_dict.items():
            value[0]['package_counts'] = []
            if value[0]['problem']['status'] == "FIXED" and \
                            self.master_hash.master_bt[bthash][0]['problem'][
                                 'status'] == "NEW":
                self.step1[bthash] = self.master_hash.master_bt[bthash]
