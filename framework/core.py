import ast
import sys
from pprint import pprint

class Core:

    master_hash = None
    slave_hash = None
    result_dict = dict()

    def __init__(self, master, slave):
        self.master_hash = master
        self.slave_hash = slave

    def run(self):
        print "Start working with data"
        self.agregate_master_bthash()
        self.master_hash.download_ureport()  # Download ureports
        self.group_data_by_bt_hash()

        # print self.result_dict

        # print pprint(self.master_hash.master_bt)

        print "All is done"
        sys.exit()

        self.prepare_data()

        for item_list in self.slave_hash.slave_bt.values():
            for item in item_list:
                if item['status'] == "closed" and item.get('status') != 0:
                    self.result_dict[item['hash']]['status'] = 1;

                self.result_dict[item['hash']]['count'] += 1  # ("Pocitat pocet vyskytu z dat")

        self.delete_item()  # Delete item with count 0
        self.sort()  # Sort data for output by Status and count
        self.generate_output()

    def sort(self):
        sorted(self.result_dict, key=lambda x: (self.result_dict[x]['status'],
                                                self.result_dict[x]['count']), reverse=True)

    def delete_item(self):
        for key, value in self.result_dict.items():
            if value.get("count") == 0:
                del self.result_dict[key]

    def prepare_data(self):
        for key_hash in self.master_hash.master_bt:
            self.result_dict[key_hash] = {'count': 0, 'status': 0}  # status - 0 NotClose, 1 Close

    def generate_output(self):
        self.master_hash.download_ureport()
        for key_hash in self.result_dict.keys():
            if key_hash in self.master_hash.master_bt:
                print "TEST", key_hash

    def agregate_master_bthash(self):
        """
        Agregate all unique bt_hash from slave servers and assign to
        master variable for downloadning ureports from master
        """
        correct_bthashes = []
        for hashes in self.slave_hash.slave_bt.values():
            for slave_bthash in hashes.keys():
                if slave_bthash not in correct_bthashes:
                    correct_bthashes.append(slave_bthash)
        self.master_hash.master_bt = correct_bthashes

    def group_data_by_bt_hash(self):
        for master_bt, master_ureport in self.master_hash.master_bt.items():
            self.result_dict[master_bt] = []
            self.result_dict[master_bt].append(master_ureport)

            for server_name, slave_report in self.slave_hash.slave_bt.items():
                if master_bt in slave_report:
                    tmp_ureport = slave_report[master_bt]
                    #tmp_ureport['source'] = server_name  # TODO Replace with
                    #  url or delete tmp_ureport variable
                    self.result_dict[master_bt].append(tmp_ureport)

    def summarize_data(self):
        pass
