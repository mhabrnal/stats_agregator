import config
import urllib2
import urllib
import json
import os.path

import sys
from aserver import AServer


class Slave(AServer):
    slave_bt = dict()

    def __init__(self):
        self.url = config.SLAVE

    def load(self, master_hash):
        if config.CACHE:
            # todo count hash of master file if isn't changed
            # Load from cache and download only missing source
            self.load_cache(master_hash)
        else:
            # Helpers variable for testing
            iteration = 1
            total = len(master_hash)
            servers = len(self.url) + 1

            for server_name, server_url in self.url.items():
                # Download from all source

                limit_from = int((iteration - 1) * round(total / servers))
                limit_to = int(iteration * round(total / servers))

                if False:
                    limit_from = 0
                    limit_to = 1

                result = self.get_ureport_by_hash(master_hash=master_hash[limit_from:limit_to],
                                                  source=server_url)

                parse_json = self.parse_hash_from_json(result)  # TODO REMAKE ??

                self.slave_bt[server_name] = parse_json
                iteration += 1

    def get_ureport_by_hash(self, master_hash, source=None):
        json_result = None

        if isinstance(self.url, dict):
            if source is not None:
                json_result = self.download_data(url=source,
                                                 data=master_hash)
        return json_result

    @staticmethod
    def download_data(url,  data):
        problem_url = url + "reports/items/"

        json_data_send = json.dumps(data)

        request = urllib2.Request(problem_url, data=json_data_send,
                                  headers={"Content-Type": "application/json",
                                           "Accept": "application/json"})

        data = urllib2.urlopen(request)

        json_string = data.read()
        return json_string

    @staticmethod
    def parse_hash_from_json(json_string):
        js = json.loads(json_string)
        return js

    def save_cache(self):
        # save hash of master
        for fname, json_str in self.slave_bt.items():
            if json_str is not None:
                f = open("cache/" + fname + ".json", "w")
                f.write(json.dumps(json_str))
                f.close()

    def load_cache(self, master_hash):
        for server_name, server_url in self.url.items():
            if os.path.isfile("cache/" + server_name + ".json"):
                f = open("cache/" + server_name + ".json", "r")
                for line in f:
                    self.slave_bt[server_name] = self.parse_hash_from_json(line)
                f.close()
            else:
                result = self.get_ureport_by_hash(master_hash=master_hash, source=server_url)
                self.slave_bt[server_name] = json.loads(result)

        self.save_cache()

    def print_debug(self):
        for s_name, s_data in self.slave_bt.items():
            print "Server " + s_name + ": \n"
            print s_data
            print "\n"
