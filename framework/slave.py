import config
import urllib2
import urllib
import json
import os.path


class Slave:
    slave_bt = dict()

    def __init__(self):
        self.url = config.SLAVE

    def load(self, master_hash):
        if config.CACHE:
            # todo count hash of master file if isn't changed
            self.load_cache(master_hash)  # Load from cache and download only missing source
        else:
            for server_name, server_url in self.url.items():
                # Download from all source
                result = self.get_ureport_by_hash(master_hash=master_hash, source=server_url)
                self.slave_bt[server_name] = json.loads(result)

    def get_ureport_by_hash(self, master_hash, source=None):
        json_result = None

        if isinstance(self.url, dict):
            if source is not None:
                json_result = self.download_data(url=source, data=master_hash)
        return json_result

    @staticmethod
    def download_data(url,  data):
        request_data = urllib.urlencode({'data': json.dumps(data)})
        request = urllib2.Request(url, request_data)
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
