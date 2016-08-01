import json
import os.path
import sys
import urllib2
import config
from aserver import AServer
from utils import *
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

        json_data = self.parse_hash_from_json(json_string=json_string)

        if 'data' in json_data:
            self.master_bt = json_data['data']
        else:
            self.master_bt = json_data

        if config.CACHE and not os.path.isfile("cache/" + self.master_file):
            save_cache(self.master_file, self.master_bt)

    def download_ureport(self):
        self.master_file = "master-complete.json"
        if config.CACHE and os.path.isfile("cache/" + self.master_file):
            cache_data = self.load_cache(self.master_file)
            if not cache_data:
                os.remove("cache/" + self.master_file)
                self.download_ureport()
            else:
                self.master_bt = cache_data
        else:
            json_str = download_data(self.url, self.master_bt)
            self.master_bt = json.loads(json_str)

            if config.CACHE:
                save_cache(self.master_file, self.master_bt)

        return True
