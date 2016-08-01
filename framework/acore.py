import subprocess
import bugzilla
from abc import ABCMeta, abstractmethod

from framework.master import Master
from framework.slave import Slave
from framework.utils import *


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

    @abstractmethod
    def run(self):
        pass

    @abstractmethod
    def generate_output(self):
        pass

    @abstractmethod
    def sort_by_count(self):
        pass

    def download_server_data(self):
        if config.CACHE and self.old_cache():
            tmp_master = self.master.load_cache(self.master.master_file)
            if not tmp_master:
                self.master.download_all_hash()
            elif 'data' in tmp_master:
                self.master.master_bt = tmp_master['data']
            else:
                self.master.master_bt = tmp_master

            for server_name, server_url in self.slave.url.items():
                tmp_slave = self.slave.load_cache(server_name + ".json")
                if tmp_slave:
                    self.slave.slave_bt[server_name] = tmp_slave
                else:
                    self.slave.download_ureports(self.master.master_bt)
        else:
            clear_cache()
            self.master.download_all_hash()
            self.slave.download_ureports(self.master.master_bt)

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

    def agregate_master_bthash(self):
        """
        Aggregate all unique bt_hash from slave servers and assign to
        master variable for downloading ureports from master
        """
        correct_bthashes = []
        for hashes in self.slave.slave_bt.values():
            for slave_bthash in hashes.keys():
                if slave_bthash not in correct_bthashes:
                    correct_bthashes.append(slave_bthash)

        self.master.master_bt = correct_bthashes

    def old_cache(self, days=30, hours=0, minutes=0):
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
                clear_cache()
                return False

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

    def group_data_by_bt_hash(self):
        for master_bt, master_ureport in self.master.master_bt.items():
            if master_ureport['report']['component'] == "will-crash":
                self.delete_bthash(master_bt)
                continue

            if get_mount_count(json_to_date(master_ureport['report']['first_occurrence']),
                               json_to_date(master_ureport['report']['last_occurrence'])) <= 1:
                self.delete_bthash(master_bt)
                continue

            # We don't want sending reports
            if master_ureport['avg_count_per_month'] <= 1:
                self.delete_bthash(master_bt)
                continue

            for server_name, slave_report in self.slave.slave_bt.items():
                if master_bt in slave_report:
                    if master_bt not in self.slave_dict:
                        self.slave_dict[master_bt] = []
                    tmp_ureport = slave_report[master_bt]
                    tmp_ureport['source'] = config.SLAVE[server_name]

                    self.slave_dict[master_bt].append(tmp_ureport)

    def output_step_1(self, data=None):
        if data:
            self.output_message += "RHEL-{0} Bugzilla bugs with closed Fedora Bugzilla bugs:\n".format("7")
            self.output_message += "------------------------------------------------------\n"

            for key_hash, ureports in data.items():
                known_bug_id = []

                master_report = self.master.master_bt[key_hash]

                for master_bug in master_report['bugs']:
                    if master_bug['type'] == "BUGZILLA" and master_bug['status'] in ['NEW', 'ASSIGNED']:

                        bz_bug = self.get_bzbug(master_bug['id'])

                        last_version = get_lastes_version(master_report['package_counts'], bz_bug.component)
                        first_version = get_first_version(master_report['package_counts'], bz_bug.component)

                        first_occurrence = json_to_date(master_report['report']['first_occurrence'])
                        last_occurrence = json_to_date(master_report['report']['last_occurrence'])

                        avg_month_counter = int(
                            round(master_report['report']['count'] / get_mount_count(first_occurrence,
                                                                                     last_occurrence)))

                        dd = date_diff(first_occurrence, last_occurrence)

                        if avg_month_counter <= 0:
                            continue

                        self.output_message += "* {0}: [{1}] - {2}\n".format(bz_bug.product, bz_bug.component,
                                                                             bz_bug.summary)

                        self.output_message += "\t- first / last affected RHEL version: {0} / {1}\n".format(
                            first_version, last_version)
                        self.output_message += "\t- first / last RHEL occurrence:       {0} / {1} ({2})\n".format(
                            first_occurrence.strftime("%Y-%m-%d"),
                            last_occurrence.strftime("%Y-%m-%d"),
                            dd)

                        self.output_message += "\t- RHEL total count:                   {0} (~{1}/month)\n".format(
                            master_report['report']['count'],
                            int(round(avg_month_counter)))

                        bugs = [bug for bug in master_report['bugs'] if bug['type'] == "BUGZILLA"
                                and bug['status'] in ['NEW', 'ASSIGNED']]

                        for b in bugs:
                            bz_bug = self.get_bzbug(b['id'])
                            self.output_message += bugzilla_url(bz_bug)

                for ureport in ureports:
                    for fedora_bug in ureport['bugs']:
                        if fedora_bug['status'] == 'CLOSED' and fedora_bug['id'] not in known_bug_id:
                            f_bug = self.get_bzbug(fedora_bug['id'])

                            known_bug_id.append(fedora_bug['id'])
                            self.output_message += "  {0}: #{1} - [{2}] - {3}\n".format(f_bug.product,
                                                                                        fedora_bug['id'],
                                                                                        f_bug.component,
                                                                                        f_bug.summary)
                            if f_bug.fixed_in:
                                self.output_message += "\t- fixed in:                           {0}\n".format(
                                    f_bug.fixed_in)
                            else:
                                self.output_message += "\t- fixed in:                           -\n"

                            self.output_message += bugzilla_url(f_bug)
            self.output_message += "\n"

    def output_step_2(self, data=None):
        # generate output for step2
        if data:
            self.output_message += "Probably fixed Bugzilla bugs in RHEL-7\n"
            self.output_message += "--------------------------------------\n"
            for key_hash, ureport in data.items():
                bugs = []
                for master_bug in ureport['bugs']:
                    if master_bug['type'] == 'BUGZILLA' and master_bug['status'] in ['NEW', 'ASSIGNED']:
                        master_report = self.master.master_bt[key_hash]

                        bz_bug = self.get_bzbug(master_bug['id'])
                        bugs.append(master_bug)

                        last_version = get_lastes_version(master_report['package_counts'],
                                                          master_report['component'])
                        first_version = get_first_version(master_report['package_counts'],
                                                          master_report['component'])

                        first_occurrence = json_to_date(master_report['report']['first_occurrence'])
                        last_occurrence = json_to_date(master_report['report']['last_occurrence'])

                        dd = date_diff(first_occurrence, last_occurrence)

                        if master_report['avg_count_per_month'] <= 0:
                            continue

                        self.output_message += "* [{0}] - {1}\n".format(bz_bug.component, bz_bug.summary)

                        self.output_message += "\t- first / last affected RHEL version: {0} / {1}\n".format(
                            first_version, last_version)

                        self.output_message += "\t- first / last RHEL occurrence:       {0} / {1} ({2})\n".format(
                            first_occurrence.strftime("%Y-%m-%d"),
                            last_occurrence.strftime("%Y-%m-%d"),
                            dd)

                        self.output_message += "\t- RHEL total count:                   {0} (~{1}/month)\n".format(
                            master_report['report']['count'], master_report['avg_count_per_month'])

                if ureport['probably_fixed']:
                    pfb = ureport['probably_fixed']['probable_fix_build']

                    self.output_message += "\t- latest RHEL version:                {0}\n".format(
                        self.get_rhel_latest_version(ureport['component']))

                    self.output_message += "\t- RHEL probably fixed in:             {0}-{1}\n".format(pfb['version'],
                                                                                                      pfb['release'])

                for b in bugs:
                    bz_bug = self.get_bzbug(b['id'])

                    self.output_message += bugzilla_url(bz_bug)

                self.output_message += "\n"

    def output_step_3(self, data=None):
        if data:
            first_loop = True
            for key_hash, value in data.items():  # step 3 contain slave's reports

                master_report = self.master.master_bt[key_hash]

                last_version = get_lastes_version(master_report['package_counts'],
                                                  master_report['component'])
                first_version = get_first_version(master_report['package_counts'],
                                                  master_report['component'])

                first_occurrence = json_to_date(master_report['report']['first_occurrence'])
                last_occurrence = json_to_date(master_report['report']['last_occurrence'])

                dd = date_diff(first_occurrence, last_occurrence)

                if master_report['avg_count_per_month'] <= 0:
                    continue

                bugs = [b for b in master_report['bugs'] if
                        b['type'] == 'BUGZILLA' and b['status'] in ['NEW', 'ASSIGNED']]

                printed = []

                for b in bugs:
                    bz_bug = self.get_bzbug(b['id'])
                    if bz_bug.id in printed:
                        continue
                    elif bz_bug.status in ['NEW', 'ASSIGNED']:
                        printed.append(bz_bug.id)  # If bug is duplicated then we return parent -> can be 2 same bug
                    else:
                        continue

                    if first_loop:
                        self.output_message += "RHEL-{0} Bugzilla bugs probably fixed in Fedora\n".format(7)
                        self.output_message += "---------------------------------------------\n"
                        first_loop = False

                    self.output_message += "*[{0}] - {1}\n".format(master_report['component'], bz_bug.summary)

                if len(printed) > 0:
                    self.output_message += "\t- first / last affected RHEL version: {0} / {1}\n".format(
                        first_version, last_version)

                    self.output_message += "\t- first / last RHEL occurrence:       {0} / {1} ({2})\n".format(
                        first_occurrence.strftime("%Y-%m-%d"),
                        last_occurrence.strftime("%Y-%m-%d"),
                        dd)

                    self.output_message += "\t- RHEL total count:                   {0} (~{1}/month)\n".format(
                        master_report['report']['count'], master_report['avg_count_per_month'])

                    printed = []
                    for b in bugs:
                        bz_bug = self.get_bzbug(b['id'])
                        if bz_bug.id in printed:
                            continue
                        else:
                            printed.append(bz_bug.id)
                        self.output_message += bugzilla_url(bz_bug)

                    sr = [s for s in self.slave_dict[key_hash] if s['probably_fixed'] is not None]
                    for s in sr:
                        pfb = s['probably_fixed']['probable_fix_build']
                        self.output_message += "\t- Fedora probably fixed in:                  {0}-{1}\n".format(
                            pfb['version'],
                            pfb['release'])

                        self.output_message += "\t- {0}reports/{1}\n".format(s['source'], s['report']['id'])

                    self.output_message += "\n"

    def output_step_4(self, data=None):
        # Resolved Fedora Bugzilla bugs appearing in RHEL-X
        if data:
            self.output_message += "Resolved Fedora Bugzilla bugs appearing in RHEL-{0}\n".format("7")
            self.output_message += "-------------------------------------------------\n"
            for key_hash, ureport in data.items():
                slave = []
                for sl in self.slave_dict[key_hash]:
                    for sb in sl['bugs']:
                        if sb['status'] == "CLOSED" and sb['type'] == "BUGZILLA" \
                                and sb['resolution'] in ['ERRATA', 'NEXTRELEASE', 'CURRENTRELEASE', 'RAWHIDE']:
                            slave.append(sl)

                if not slave:
                    continue

                master_report = self.master.master_bt[key_hash]

                last_version = get_lastes_version(master_report['package_counts'],
                                                  master_report['component'])

                first_version = get_first_version(master_report['package_counts'],
                                                  master_report['component'])

                first_occurrence = json_to_date(master_report['report']['first_occurrence'])
                last_occurrence = json_to_date(master_report['report']['last_occurrence'])

                dd = date_diff(first_occurrence, last_occurrence)

                if master_report['avg_count_per_month'] <= 0:
                    continue

                printed = []
                for s in slave:
                    for sb in s['bugs']:
                        bz_bug = self.get_bzbug(sb['id'])
                        if bz_bug.id in printed:
                            continue
                        else:
                            printed.append(bz_bug.id)

                        if bz_bug and bz_bug.status == 'CLOSED' and bz_bug.resolution in ['ERRATA', 'NEXTRELEASE',
                                                                                          'CURRENTRELEASE', 'RAWHIDE']:

                            self.output_message += "* [{0}] - {1}\n".format(master_report['report']['component'],
                                                                            bz_bug.summary)

                            self.output_message += "\t- first / last affected RHEL version: {0} / {1}\n".format(
                                first_version, last_version)

                            self.output_message += "\t- first / last RHEL occurrence:       {0} / {1} ({2})\n".format(
                                first_occurrence.strftime("%Y-%m-%d"),
                                last_occurrence.strftime("%Y-%m-%d"),
                                dd)

                            self.output_message += "\t- RHEL total count:                   {0} (~{1}/month)\n".format(
                                master_report['report']['count'], master_report['avg_count_per_month'])

                            self.output_message += "\t- https://faf-report.itos.redhat.com/reports/{0}\n".format(
                                master_report['report']['id'])

                            self.output_message += "\t- Fedora fixed in:                     {0}\n".format(
                                strip_name_from_version(bz_bug.fixed_in))
                            last_version = get_lastes_version(ureport['package_counts'], master_report['component'])

                            self.output_message += bugzilla_url(bz_bug)
                            self.output_message += "\n"

    def output_step_5(self, data=None):
        if data:
            self.output_message += "\nTraces occurring on CentOS-{0} that are fixed in Fedora\n".format("7")
            self.output_message += "-----------------------------------------------------\n"
            for key_hash, ureport in data.items():
                slave_bug = [sb for sb in self.slave_dict[key_hash][0]['bugs'] if
                             sb['type'] == "BUGZILLA" and sb['resolution'] in ['ERRATA', 'NEXTRELEASE',
                                                                               'CURRENTRELEASE', 'RAWHIDE']]
                if not slave_bug:
                    continue
                master_report = self.master.master_bt[key_hash]

                last_version = get_lastes_version(master_report['package_counts'],
                                                  master_report['component'])

                first_version = get_first_version(master_report['package_counts'],
                                                  master_report['component'])

                first_occurrence = json_to_date(master_report['report']['first_occurrence'])
                last_occurrence = json_to_date(master_report['report']['last_occurrence'])

                try:
                    avg_month_counter = int(round(master_report['report']['count'] / get_mount_count(first_occurrence,
                                                                                                     last_occurrence)))
                except:
                    continue

                if avg_month_counter <= 0:
                    continue

                for sb in slave_bug:
                    bz_bug = self.get_bzbug(sb['id'])
                    self.output_message += "* [{0}] - {1}\n".format(master_report['report']['component'],
                                                                    bz_bug.summary)

                    self.output_message += "\t- first / last affected RHEL version: {0} / {1}\n".format(
                        first_version, last_version)

                    self.output_message += "\t - fixed in: {0}\n".format(bz_bug.fixed_in)
                    last_version = get_lastes_version(ureport['package_counts'], master_report['component'])
                    self.output_message += "\t - last affected version: {0}\n".format(last_version)
                    self.output_message += bugzilla_url(bz_bug)

    def output_step_6(self, data=None):
        # Traces occurring on RHEL-${X} that are probably fixed in Fedora:
        if data:
            self.output_message += "Traces occurring on RHEL-{0} that are probably fixed in Fedora\n".format("7")
            self.output_message += "------------------------------------------------------------\n"
            for key_hash, ureport in data.items():

                slave_pf = [spf for spf in self.slave_dict[key_hash] if spf['probably_fixed'] is not None]
                if not slave_pf:
                    continue

                master_report = self.master.master_bt[key_hash]

                last_version = get_lastes_version(master_report['package_counts'],
                                                  master_report['component'])

                first_version = get_first_version(master_report['package_counts'],
                                                  master_report['component'])

                first_occurrence = json_to_date(master_report['report']['first_occurrence'])
                last_occurrence = json_to_date(master_report['report']['last_occurrence'])

                dd = date_diff(first_occurrence, last_occurrence)

                avg_month_counter = int(round(master_report['report']['count'] / get_mount_count(first_occurrence,
                                                                                                 last_occurrence)))
                if avg_month_counter <= 0:
                    continue

                for spf in slave_pf:
                    pf = spf['probably_fixed']['probable_fix_build']

                    if master_report['component'] != pf['base_package_name'] and False:
                        continue

                    self.output_message += "* [{0}] - {1}\n".format(master_report['report']['component'],
                                                                    master_report['crash_function'])

                    self.output_message += "\t- first / last affected RHEL version: {0} / {1}\n".format(
                        first_version, last_version)

                    self.output_message += "\t- first / last RHEL occurrence:       {0} / {1} ({2})\n".format(
                        first_occurrence.strftime("%Y-%m-%d"),
                        last_occurrence.strftime("%Y-%m-%d"),
                        dd)

                    self.output_message += "\t- RHEL total count:                   {0} (~{1}/month)\n".format(
                        master_report['report']['count'],
                        int(round(avg_month_counter)))

                    self.output_message += "\t- latest RHEL version:                {0}\n".format(
                        self.get_rhel_latest_version(ureport['component']))

                    self.output_message += "\t- https://faf-report.itos.redhat.com/reports/{0}\n".format(
                        master_report['report']['id'])

                    self.output_message += "\t- Fedora probably fixed in:           {0}\n".format(
                        strip_name_from_version(pf['nvr']))

                    self.output_message += "\t- {0}reports/{1}\n\n".format(spf['source'], spf['report']['id'])
            self.output_message += "\n"

    def output_step_7(self, data=None):
        if data:
            self.output_message += "Traces occurring on CentOS-{0} that are probably fixed in Fedora\n".format("7")
            self.output_message += "--------------------------------------------------------------\n"
            for key_hash, ureport in data.items():

                slave_pf = [spf for spf in self.slave_dict[key_hash] if spf['probably_fixed'] is not None]
                if not slave_pf:
                    continue

                master_report = self.master.master_bt[key_hash]

                last_version = get_lastes_version(master_report['package_counts'],
                                                  master_report['component'])

                first_version = get_first_version(master_report['package_counts'],
                                                  master_report['component'])

                first_occurrence = json_to_date(master_report['report']['first_occurrence'])
                last_occurrence = json_to_date(master_report['report']['last_occurrence'])

                dd = date_diff(first_occurrence, last_occurrence)

                if master_report['avg_count_per_month'] <= 0:
                    continue

                for spf in slave_pf:
                    self.output_message += "* [{0}] - {1}\n".format(master_report['report']['component'],
                                                                    master_report['crash_function'])

                    self.output_message += "\t- first / last affected RHEL version: {0} / {1}\n".format(
                        first_version, last_version)

                    self.output_message += "\t- first / last RHEL occurrence:       {0} / {1} ({2})\n".format(
                        first_occurrence.strftime("%Y-%m-%d"),
                        last_occurrence.strftime("%Y-%m-%d"),
                        dd)

                    self.output_message += "\t- RHEL total count:                   {0} (~{1}/month)\n".format(
                        master_report['report']['count'], master_report['avg_count_per_month'])

                    self.output_message += "\t- latest RHEL version:                {0}\n".format(
                        self.get_rhel_latest_version(ureport['component']))

                    self.output_message += "\t- https://faf-report.itos.redhat.com/reports/{0}\n".format(
                        master_report['report']['id'])

                    pf = spf['probably_fixed']['probable_fix_build']

                    self.output_message += "\t- probably fixed in: {0}-{1}\n".format(pf['version'], pf['release'])

                    last_version = get_lastes_version(ureport['package_counts'], master_report['component'])
                    self.output_message += "\t- last affected version: {0}\n".format(last_version)
                    self.output_message += "\t- {0}reports/{1}\n\n".format(self.master.url,
                                                                           ureport['report']['id'])  # NA BZ

    def output_step_8(self, data=None):
        step_count_8 = 0
        if data:
            self.output_message += "\nFedora Bugzilla bugs and CentOS bugs appearing in RHEL-{0}\n".format("7")
            self.output_message += "--------------------------------------------------------\n"
            for key_hash, ureport in data.items():
                if step_count_8 >= 20:
                    continue

                slave_pf = [spf for spf in self.slave_dict[key_hash]]  # if spf['probably_fixed'] is not None

                master_report = self.master.master_bt[key_hash]

                last_version = get_lastes_version(master_report['package_counts'],
                                                  master_report['component'])

                first_version = get_first_version(master_report['package_counts'],
                                                  master_report['component'])

                first_occurrence = json_to_date(master_report['report']['first_occurrence'])
                last_occurrence = json_to_date(master_report['report']['last_occurrence'])

                dd = date_diff(first_occurrence, last_occurrence)

                if master_report['avg_count_per_month'] <= 0:
                    continue

                self.output_message += "* [{0}] - {1}\n".format(master_report['report']['component'],
                                                                master_report['crash_function'])

                self.output_message += "\t- first / last affected RHEL version: {0} / {1}\n".format(
                    first_version, last_version)

                self.output_message += "\t- first / last RHEL occurrence:       {0} / {1} ({2})\n".format(
                    first_occurrence.strftime("%Y-%m-%d"),
                    last_occurrence.strftime("%Y-%m-%d"),
                    dd)

                self.output_message += "\t- RHEL total count:                   {0} (~{1}/month)\n".format(
                    master_report['report']['count'], master_report['avg_count_per_month'])

                self.output_message += "\t- https://faf-report.itos.redhat.com/reports/{0}\n".format(
                    master_report['report']['id'])

                for spf in slave_pf:
                    last_slave_version = get_lastes_version(spf['package_counts'], master_report['component'])
                    first_slave_version = get_first_version(spf['package_counts'], master_report['component'])

                    first_slave_occurrence = json_to_date(spf['report']['first_occurrence'])
                    last_slave_occurrence = json_to_date(spf['report']['last_occurrence'])

                    slave_date_diff = date_diff(first_slave_occurrence, last_slave_occurrence)

                    self.output_message += "\t- first/last affected Fedora version: {0}/{1}\n".format(
                        first_slave_version, last_slave_version)

                    self.output_message += "\t- first / last Fedora occurrence:     {0}/{1} ({2})\n".format(
                        first_slave_occurrence.strftime("%Y-%m-%d"), last_slave_occurrence.strftime("%Y-%m-%d"),
                        slave_date_diff)

                    self.output_message += "\t- Fedora total count:                 {0} (~{1}/month)\n".format(
                        spf['report']['count'], spf['avg_count_per_month'])

                    for bug in spf['bugs']:
                        if bug['type'] == "BUGZILLA":
                            bz_bug = self.get_bzbug(bug['id'])
                            if not bz_bug:
                                continue
                            self.output_message += bugzilla_url(bz_bug)

                        elif bug['type'] == "MANTIS":
                            # TODO implement mantis api
                            pass

                self.output_message += "\n"
                step_count_8 += 1
