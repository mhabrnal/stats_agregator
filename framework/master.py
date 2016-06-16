import config
import urllib2
import json
import os.path
import sys
from datetime import datetime, timedelta
from aserver import AServer
from pprint import pprint


class Master(AServer):

    master_file = "master_small.json"

    def __init__(self):
        self.url = config.MASTER

    def download_all_hash(self):
        """
        Download all json from master server.
        """
        # get hash have parameters (OS, RELEASE, DATE FROM, DATE TO)
        url = self.url + "reports/get_hash/*/*/2015-12-01"
        request = urllib2.Request(url,
                                  headers={"Accept": "application/json"})

        try:
            data = urllib2.urlopen(request)
        except urllib2.URLError as e:
            print "{0} - {1}".format(url, e.reason)
            sys.exit()
        except urllib2.HTTPError as e:
            print "Url {0} return code {1}".format(url, e.code)
            sys.exit()

        json_string = data.read()

        self.parse_hash_from_json(json_string=json_string)

        if config.CACHE and not os.path.isfile("cache/" + self.master_file):
            self.save_cache(self.master_file, self.master_bt)

    def parse_hash_from_json(self, json_string):
        self.master_bt = (json.loads(json_string))
        if 'data' in self.master_bt:
            self.master_bt = self.master_bt['data']
        else:
            self.master_bt = self.master_bt

    def load_cache(self):
        if os.path.isfile("cache/" + self.master_file):
            with open("cache/" + self.master_file, "r") as f:
                for line in f:
                    self.parse_hash_from_json(line)
            return True
        else:
            return False

    def download_ureport(self):
        self.master_file = "master-complete.json"
        if config.CACHE and os.path.isfile("cache/" + self.master_file):
            self.load_cache()
        else:
            json_str = self.download_data(self.url, self.master_bt)
            self.master_bt = json.loads(json_str)

            if config.CACHE:
                self.save_cache(self.master_file, self.master_bt)

        return True

    def download_problems(self, opsys=None, date_range=None):
        url = self.url + "problems/?bug_filter=NO_BUGS"

        if opsys:
            if isinstance(opsys, list):
                for os in opsys:
                    url += "&opsys=" + os.replace(" ", "+")
            elif isinstance(opsys, basestring):
                url += "&opsys=" + opsys.replace(" ", "+")
            else:
                raise "Unknown attribute for OS!"
        if date_range:
            url += "&daterange=" + date_range

        request = urllib2.Request(url, headers={"Accept": "application/json"})

        try:
            data = urllib2.urlopen(request)
        except urllib2.URLError as e:
            print "{0} - {1}".format(url, e.reason)
            sys.exit()
        except urllib2.HTTPError as e:
            print "Url {0} return code {1}".format(url, e.code)
            sys.exit()

        json_string = data.read()

        pure_data = json.loads(json_string)

        for problem in pure_data['problems']:
            problem_url = self.url + "problems/" + str(problem['id'])
            p_request = urllib2.Request(problem_url, headers={"Accept": "application/json"})

            problem_string = urllib2.urlopen(p_request).read()

            self.master_problem.append(json.loads(problem_string))
