import config
import urllib2
import urllib
import json
import os.path
from pprint import pprint
import sys
from aserver import AServer


class Slave(AServer):

    def __init__(self):
        self.url = config.SLAVE

    def download_ureports(self, master_bt):
        # Helpers variable for testing
        iteration = 1
        total = len(master_bt)
        servers = len(self.url) + 1

        if config.VERBOSE:
            print "Celkem je {0} master hashu".format(total)

        for server_name, server_url in self.url.items():
            # Download from all source

            limit_from = int((iteration - 1) * round(total / servers))
            limit_to = int(iteration * round(total / servers))

            if True:
                limit_from = 0
                limit_to = 100

            result = self.get_ureport_by_hash(master_hash=master_bt[limit_from:limit_to],
                                              source=server_url)

            parse_json = self.parse_hash_from_json(result)  # TODO REMAKE ??

            self.slave_bt[server_name] = parse_json

            if config.CACHE:
                self.save_cache(server_name + ".json", parse_json)

            iteration += 1

    def get_ureport_by_hash(self, master_hash, source=None):
        json_result = None

        if isinstance(self.url, dict):
            if source is not None:
                json_result = self.download_data(url=source,
                                                 data=master_hash)
        return json_result

    @staticmethod
    def parse_hash_from_json(json_string):
        js = json.loads(json_string)
        return js

    def load_cache(self):
        for server_name, server_url in self.url.items():
            if os.path.isfile("cache/" + server_name + ".json"):
                with open("cache/" + server_name + ".json", "r") as f:
                    for line in f:
                        self.slave_bt[server_name] = self.parse_hash_from_json(line)
                return True
            else:
                return False

    def get_problem_info(self, problem_bt_hash):
        for s_name, s_url in self.url.items():
            problem_url = s_url + "/problems/bthash/?" + problem_bt_hash + "&bth=f3f5e5020c0f69f71c66fe33e47d232435c451a0"

            p_request = urllib2.Request(problem_url, headers={"Accept": "application/json"})

            problem_string = urllib2.urlopen(p_request).read()

            problem = json.loads(problem_string)

            tmp_list = []
            if "multiple" in problem:
                for p_id in problem['multiple']:
                    tmp_list.append(self.get_problem_by_id(s_url, p_id))
            else:
                tmp_list.append(problem)

            self.slave_problem[problem_bt_hash] = tmp_list

    def download_problems(self, master_problem):
        for p in master_problem:
            self.get_problem_info(p['bt_hash_qs'])

    @staticmethod
    def get_problem_by_id(s_url, p_id):
        problem_url = s_url + "/problems/" + str(p_id)

        p_request = urllib2.Request(problem_url, headers={"Accept": "application/json"})

        return json.loads(urllib2.urlopen(p_request).read())

