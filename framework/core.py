import sys
import ast

class Core:

    master_hash = None
    slave_hash = None
    result_dict = dict()

    def __init__(self, master, slave):
        self.master_hash = master
        self.slave_hash = slave

    def run(self):
        self.prepare_data()

        for items in self.slave_hash.slave_bt.values():
            if isinstance(items, dict):
                for key_hash, data in items.iteritems():
                    data = ast.literal_eval(data)
                    if data['status'] == "closed" and data.get('status') != 0:
                        self.result_dict[key_hash]['status'] = 1;

                    self.result_dict[key_hash]['count'] += 1  # ("Pocitat pocet vyskytu z dat")

        self.delete_item()  # Delete item with count 0
        self.sort()
        self.generate_output()

    def sort(self):
        sorted(self.result_dict, key=lambda x: (self.result_dict[x]['status'], self.result_dict[x]['count']), reverse=True)

    def delete_item(self):
        for key, value in self.result_dict.items():
            if value.get("count") == 0:
                del self.result_dict[key]

    def prepare_data(self):
        for key_hash in self.master_hash.master_bt:
            self.result_dict[key_hash] = {'count': 0, 'status': 0}  # 0 NotClose, 1 Close

    def generate_output(self):
        self.master_hash.download_ureport()
        for key_hash in self.result_dict.keys():
            if key_hash in self.master_hash.master_bt:
                print "TEST"
