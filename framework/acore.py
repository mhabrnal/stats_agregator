from abc import ABCMeta, abstractmethod
from framework.master import Master
from framework.slave import Slave
from framework.utils import *
import collections
import subprocess
import bugzilla
import config


class ACore:
    __metaclass__ = ABCMeta

    master = None
    slave = None
    bz = None
    bz_bugs = dict()
    components = dict()
    slave_dict = dict()

    already_processed = []
    # Data for separate steps

    output_message = ""

    def __init__(self):
        self.master = Master()
        self.slave = Slave()
        self.bz = bugzilla.Bugzilla(url="https://bugzilla.redhat.com/xmlrpc.cgi",
                                    cookiefile=None)

        self.bz.login(config.BZ_USER, config.BZ_PASSWORD)

    def download_data(self):
        if config.CACHE and self.old_cache():

            if not self.master.load_cache():
                self.master.download_all_hash()

            if not self.slave.load_cache():
                self.slave.download_ureports(self.master.master_bt)
        else:
            clear_cache()
            self.master.download_all_hash()
            self.slave.download_ureports(self.master.master_bt)

    @abstractmethod
    def run(self):
        pass

    @abstractmethod
    def generate_output(self):
        pass

    def send_data_to_mail(self):
        import smtplib
        from email.mime.text import MIMEText

        msg = MIMEText(self.output_message)

        msg['Subject'] = "ABRT Mail stats"
        msg['From'] = "phelia@redhat.com"
        msg['To'] = "phelia@redhat.com"

        s = smtplib.SMTP('localhost')
        s.sendmail('phelia@redhat.com', 'phelia@redhat.com', msg.as_string())
        s.quit()

    def old_cache(self, days=10, hours=0, minutes=0):
        """
        If master file is older then parametrized time,
        then delete all cached files.
        By default is set on 3 hours
        """
        if os.path.isfile(self.master.master_file):
            modify_datetime = datetime.fromtimestamp(
                os.path.getmtime(self.master.master_file))
            current_datetime = datetime.now()

            result = current_datetime - modify_datetime

            if result.total_seconds() > timedelta(minutes=minutes,
                                                  hours=hours,
                                                  days=days).total_seconds():
                self.clear_cache()

        return True

    def get_bzbug(self, id):
        if id in self.bz_bugs:
            bug = self.bz_bugs[id]
        else:
            try:
                bug = self.bz.getbug(id)
                self.bz_bugs[id] = bug
                print "Bug {0} was downloaded".format(id)
            except:
                return False

        if bug.resolution in ["DUPLICATE"]:
            bug = self.get_bzbug(bug.dupe_of)
        return bug

    def sort_by_count(self):
        for i in range(1, 9):
            if len(getattr(self, "step" + str(i))) > 0:
                step = getattr(self, "step" + str(i))
                step = collections.OrderedDict(
                    sorted(step.items(), key=lambda item: int(item[1]['avg_count_per_month']), reverse=True))
                setattr(self, "step" + str(i), step)

    def get_rhel_latest_version(self, component):
        if component in self.components:
            return self.components[component]
        else:
            bash_command = "brew latest-build rhel-7.3 {0} --quiet".format(component)
            process = subprocess.Popen(bash_command.split(), stdout=subprocess.PIPE)
            strip_version = strip_name_from_version(process.communicate()[0].split()[0])
            self.components[component] = strip_version
            return strip_version

    def delete_bthash(self, bt_hash):
        del (self.master.master_bt[bt_hash])

    def save_output_to_disk(self):
        with open("output.txt", "w") as f:
            f.write(self.output_message)
