import config
import urllib2
import json
import os.path


class Master:
    master_bt = []

    def __init__(self):
        self.url = config.MASTER

    def load(self):
        if config.CACHE:
            self.load_cache()
        else:
            self.download_all_hash()
            # delete master json

    def download_all_hash(self):
        '''
        Download all json from master server.
        '''
        data = urllib2.urlopen(self.url)
        json_string = data.read()
        self.parse_hash_from_json(json_string=json_string)

        if config.CACHE:
            self.save_cache()

    def parse_hash_from_json(self, json_string):
        self.master_bt = (json.loads(json_string))

    def save_cache(self):
        if self.master_bt is not None:
            f = open("cache/master.json", "w")
            f.write(json.dumps(self.master_bt))
            f.close()

    def load_cache(self):
        if os.path.isfile("cache/master.json"):
            f = open("cache/master.json", "r")
            for line in f:
                self.parse_hash_from_json(line)
        else:
            self.download_all_hash()

    def download_ureport(self):
        pass
