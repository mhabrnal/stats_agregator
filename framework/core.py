import config
import sys
from pprint import pprint
import bugzilla
import re
import subprocess
import os
from datetime import datetime, timedelta
from framework.master import Master
from framework.slave import Slave

class Core:

    master = None
    slave = None
    bz_bugs = dict()
    slave_dict = dict()

    # Data for separate steps
    step1 = dict()  # Bugzilla bugs with closed Fedora Bugzilla bugs
    step2 = dict()  # Bugzilla bugs probably fixed in RHEL
    step3 = dict()  # Bugzilla bugs probably fixed in fedora
    step4 = dict()  # Traces occurring on RHEL-${X} that are fixed in Fedora:
    step5 = dict()  # Traces occurring on CentOS-${X} that are fixed in Fedora:
    step6 = dict()  # Traces occurring on RHEL-${X} that are probably fixed in Fedora:
    step7 = dict()  # Traces occurring on CentOS-${X} that are probably fixed in Fedora:

    output_message = ""

    def __init__(self):
        self.master = Master()
        self.slave = Slave()

    def download_data(self):
        if config.CACHE and self.old_cache():

            if not self.master.load_cache():
                self.master.download_all_hash()

            if not self.slave.load_cache():
                self.slave.download_ureports(self.master.master_bt)
        else:
            self.clear_cache()
            self.master.download_all_hash()
            self.slave.download_ureports(self.master.master_bt)

    def run(self):
        self.download_data()

        print "Start working with data"

        self.agregate_master_bthash()
        self.master.download_ureport()  # Download ureports
        self.group_data_by_bt_hash()
        self.summarize_data()

        # Save master data to cache
        if os.path.isfile("cache/master_problem.json") and config.CACHE:
            # Load
            self.master.master_problem = self.master.fast_load("master_problem.json")
        else:
            self.master.download_problems(opsys=config.OPSYS[2],
                                          date_range="2015-07-31%3A2016-05-18")
            if config.CACHE:
                self.master.save_cache("master_problem.json", self.master.master_problem)

        if os.path.isfile("cache/slave_problem.json") and config.CACHE:
            # Load
            self.slave.slave_problem = self.slave.fast_load("slave_problem.json")
        else:
            self.slave.download_problems(self.master.master_problem)

            if config.CACHE:
                self.slave.save_cache("slave_problem.json", self.slave.slave_problem)

        self.generate_output()

        # self.send_data_to_mail()

        sys.exit()

    def generate_output(self):
        # TODO Implement cache of bz bugs
        bz = bugzilla.Bugzilla(url="https://bugzilla.redhat.com/xmlrpc.cgi",
                               cookiefile=None)
        bz.login(config.BZ_USER, config.BZ_PASSWORD)

        if self.step1:
            self.output_message += "RHEL-{0}.{1} Bugzilla bugs with closed Fedora Bugzilla " \
                                   "bugs:\n".format("7", "x")

            for key_hash, ureports in self.step1.items():
                known_bug_id = []

                master_report = self.master.master_bt[key_hash]

                for master_bug in master_report['bugs']:
                    if master_bug['type'] == "BUGZILLA" and master_bug['status'] \
                            == 'NEW':  # TODO remove TYPE VERIFICATION

                        bz_bug = bz.getbug(master_bug['id'])

                        self.output_message += "* {0}: #{1} - [{2}] - {3}\n".format(bz_bug.product,
                                                                                    master_bug['id'],
                                                                                    bz_bug.component,
                                                                                    bz_bug.summary)

                        last_version = ""

                        for item in master_report['package_counts']:
                            match = re.search("^" + bz_bug.component, item[0])
                            if match:
                                item[-1].sort(key=lambda x: x[0])
                                last_version = item[-1][0][0]

                        self.output_message += "\t- last affected version: {0}\n".format(last_version)

                for ureport in ureports:
                    for fedora_bug in ureport['bugs']:
                        if fedora_bug['status'] == 'CLOSED' and fedora_bug['id'] \
                                not in known_bug_id:
                            f_bug = bz.getbug(fedora_bug['id'])
                            known_bug_id.append(fedora_bug['id'])
                            self.output_message += "  {0}: #{1} - [{2}] - {3}\n".format(f_bug.product,
                                                                                        fedora_bug['id'],
                                                                                        f_bug.component,
                                                                                        f_bug.summary)
                            if f_bug.fixed_in:
                                self.output_message += "\t- fixed in: {0}\n".format(f_bug.fixed_in)
                            else:
                                self.output_message += "\t- fixed in: -\n"

        # generate output for step2
        if self.step2:
            self.output_message += "\nProbably fixed Bugzilla bugs in RHEL-7\n"
            for key_hash, ureport in self.step2.items():
                for master_bug in ureport['bugs']:
                    if master_bug['type'] == 'BUGZILLA' and master_bug['status'] == 'NEW':
                        bz_bug = bz.getbug(master_bug['id'])

                        self.output_message += "* #{0} - [{1}] - {2}\n".format(master_bug['id'], bz_bug.component, bz_bug.summary)

                        last_version = ""
                        for item in ureport['package_counts']:
                            if re.search("^" + bz_bug.component, item[0]):
                                item[-1].sort(key=lambda x: x[0])
                                last_version = item[-1][0][0]

                        self.output_message += "\t- last affected version: {0}\n".format(last_version)

                if ureport['probably_fixed']:
                    pfb = ureport['probably_fixed']['probable_fix_build']
                    self.output_message += "\t- probably fixed in: {0}:{1}-{2}\n".format(pfb['epoch'], pfb['version'],
                                                                                         pfb['release'])

                    bash_command = "brew latest-build rhel-7.3 {0} --quiet".format(ureport['component'])
                    process = subprocess.Popen(bash_command.split(), stdout=subprocess.PIPE)
                    self.output_message += "\t- latest version : {0}\n".format(process.communicate()[0].split()[0])

        # generate output for step3
        if self.step3:
            self.output_message += "\nProbably fixed Bugzilla bugs in Fedora\n"
            for key_hash, value in self.step3.items():  # step 3 contain slave's reports
                ureport, probably_fixed, bugs = value
                master_report = self.master.master_bt[key_hash]

                # TODO: add 'component' to 'packate_counts' in FAF

                for b in bugs:
                    bz_bug = bz.getbug(b['id'])
                    self.output_message += "* #{0} - [{1}] - {2}\n".format(bz_bug.id, master_report['component'], bz_bug.summary)

                    self.output_message += "* #{0} - [{1}] - {2}\n".format(master_bug['id'], master_report['component'],
                                                                           bz_bug.summary)
                    self.output_message += "\t- last affected version: {0}\n".format(last_version)
                    self.output_message += "\t- probably fixed in: {0}:{1}-{2}\n".format(pfb['epoch'], pfb['version'],
                                                                                         pfb['release'])

            pfb = probably_fixed['probable_fix_build']
            last_version = self.get_lastes_version(ureport[0]['package_counts'], master_report['component'])
            self.output_message += "\t- last affected version: {0}\n".format(last_version)
            self.output_message += "\t- probably fixed in: {0}:{1}-{2}\n\n".format(pfb['epoch'], pfb['version'],
                                                                                   pfb['release'])

        if self.step4:
            self.output_message += "\nTraces occurring on RHEL-${0} that are fixed in Fedora\n".format("7")
            for key_hash, ureport in self.step4.items():
                slave_bug = [sb for sb in self.slave_dict[key_hash][0]['bugs'] if sb['type'] == "BUGZILLA" and sb['resolution'] in ['ERRATA']]
                if not slave_bug:
                    continue
                master_report = self.master.master_bt[key_hash]

                for sb in slave_bug:
                    bz_bug = bz.getbug(sb['id'])
                    self.output_message += "* [{0}] - {1}\n".format(master_report['report']['component'], bz_bug.summary)
                    self.output_message += "\t - fixed in: {0}\n".format(bz_bug.fixed_in)
                    last_version = self.get_lastes_version(ureport['package_counts'], master_report['component'])
                    self.output_message += "\t - last affected version: {0}\n".format(last_version)
                    self.output_message += "\t - {0}reports/{1}\n".format(self.master.url, ureport['report']['id'])

        if self.step5:
            self.output_message += "\nTraces occurring on CentOS-${0} that are fixed in Fedora\n".format("7")
            for key_hash, ureport in self.step5.items():
                slave_bug = [sb for sb in self.slave_dict[key_hash][0]['bugs'] if
                             sb['type'] == "BUGZILLA" and sb['resolution'] in ['ERRATA']]
                if not slave_bug:
                    continue
                master_report = self.master.master_bt[key_hash]

                for sb in slave_bug:
                    bz_bug = bz.getbug(sb['id'])
                    self.output_message += "* [{0}] - {1}\n".format(master_report['report']['component'], bz_bug.summary)
                    self.output_message += "\t - fixed in: {0}\n".format(bz_bug.fixed_in)
                    last_version = self.get_lastes_version(ureport['package_counts'], master_report['component'])
                    self.output_message += "\t - last affected version: {0}\n".format(last_version)
                    self.output_message += "\t - {0}reports/{1}\n".format(self.master.url, ureport['report']['id'])

        if self.step6:
            self.output_message += "\nTraces occurring on RHEL-${0} that are probably fixed in Fedora\n".format("7")
            for key_hash, ureport in self.step6.items():

                slave_pf = [spf for spf in self.slave_dict[key_hash] if spf['probably_fixed'] is not None]
                if not slave_pf:
                    continue

                master_report = self.master.master_bt[key_hash]

                for spf in slave_pf:
                    self.output_message += "* [{0}] - {1}\n".format(master_report['report']['component'], "")
                    pf = spf['probably_fixed']['probable_fix_build']
                    self.output_message += "\t - probably fixed in: {0}:{1}-{2}\n".format(pf['epoch'], pf['version'],
                                                                                          pf['release'])
                    last_version = self.get_lastes_version(ureport['package_counts'], master_report['component'])
                    self.output_message += "\t - last affected version: {0}\n".format(last_version)
                    self.output_message += "\t - {0}reports/{1}\n".format(self.master.url, ureport['report']['id'])

        if self.step7:
            self.output_message += "\nTraces occurring on CentOS-${0} that are probably fixed in Fedora\n".format("7")
            for key_hash, ureport in self.step7.items():

                slave_pf = [spf for spf in self.slave_dict[key_hash] if spf['probably_fixed'] is not None]
                if not slave_pf:
                    continue

                master_report = self.master.master_bt[key_hash]

                for spf in slave_pf:
                    self.output_message += "* [{0}] - {1}\n".format(master_report['report']['component'], "")
                    pf = spf['probably_fixed']['probable_fix_build']
                    self.output_message += "\t - probably fixed in: {0}:{1}-{2}\n".format(pf['epoch'], pf['version'],
                                                                                          pf['release'])
                    last_version = self.get_lastes_version(ureport['package_counts'], master_report['component'])
                    self.output_message += "\t - last affected version: {0}\n".format(last_version)
                    self.output_message += "\t - {0}reports/{1}\n".format(self.master.url, ureport['report']['id'])

        print self.output_message

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

    def group_data_by_bt_hash(self):
        for master_bt, master_ureport in self.master.master_bt.items():
            for server_name, slave_report in self.slave.slave_bt.items():
                if master_bt in slave_report:
                    if master_bt not in self.slave_dict:
                        self.slave_dict[master_bt] = []
                    tmp_ureport = slave_report[master_bt]
                    #  tmp_ureport['source'] = server_name  # TODO Replace with
                    #  TODO url or delete tmp_ureport variable
                    self.slave_dict[master_bt].append(tmp_ureport)

    # TODO REPLACE STEP x FOR VALID COMMENT
    def summarize_data(self):
        # Step 1
        for bthash, value in self.slave_dict.items():
            if bthash in self.step1:
                continue  # Data will be filled in next step

            for report in value:
                if 'bugs' not in report:
                    continue  # Don't iterate reports without bugs
                # Search bugzilla bug with closed fedora bugzilla bug
                for bug in report['bugs']:
                    if bug['resolution'] in config.BUG_TYPE:
                        # Try to find bugs in master
                        if 'bugs' in self.master.master_bt[bthash]:
                            for master_bug in self.master.master_bt[bthash]['bugs']:
                                # what about ASSIGNED bugs? will those be included?
                                if master_bug['status'] == "NEW" and \
                                        master_bug['type'] == 'BUGZILLA':
                                    atleast_one_new = True

                                    # TODO DELETE THIS LINE
                                    self.step1[bthash] = self.slave_dict[bthash]
                    else:
                        all_bugs_closed = False

                if all_bugs_closed and atleast_one_new:
                    self.step1[bthash] = self.slave_dict[bthash]

        # Step 2
        for bthash, report in self.master.master_bt.items():
            if bthash not in self.step1 and report['probably_fixed'] is not None and 'bugs' in report:
                for bug in report['bugs']:
                    if bug['type'] == 'BUGZILLA' and bug['status'] != 'CLOSED':
                        self.step2[bthash] = report

        # Step 3
        for bthash, report in self.master.master_bt.items():
            if (bthash not in self.step1 and bthash not in self.step2) and 'bugs' in report:
                pf = [r['probably_fixed'] for r in self.slave_dict[bthash] if r['probably_fixed'] is not None]
                if not pf:
                    continue

                bugs = [b for b in report['bugs'] if b['type'] == 'BUGZILLA' and b['status'] in ('NEW', 'ASSIGNED')]
                if not bugs:
                    continue

                pf = sorted(pf, key=lambda ver: "-".join(ver))
                self.step3[bthash] = (self.slave_dict[bthash], pf[0], bugs)

        # Step 4
        for bthash, ureport in self.master.master_bt.items():
            occurring_os = self.get_opsys(ureport['releases'])

            if len(ureport['report']['bugs']) == 0 and "Red Hat Enterprise Linux" in occurring_os:
                for s in self.slave_dict[bthash]:
                    if 'bugs' not in s:
                        continue

                    bugs = [b for b in s['bugs'] if b['type'] == "BUGZILLA" and b['status'] in ['CLOSED'] and b['resolution'] in ['ERRATA']]
                    if not bugs:
                        continue

                    self.step4[bthash] = ureport

        # Step 5
        for bthash, ureport in self.master.master_bt.items():
            occurring_os = self.get_opsys(ureport['releases'])
            if len(ureport['report']['bugs']) == 0 and "CentOS" in occurring_os:
                for s in self.slave_dict[bthash]:
                    if 'bugs' not in s:
                        continue

                    bugs = [b for b in s['bugs'] if
                            b['type'] == "BUGZILLA" and b['status'] in ['CLOSED'] and b['resolution'] in ['ERRATA']]
                    if not bugs:
                        continue

                    self.step5[bthash] = ureport

        # Step 6
        for bthash, ureport in self.master.master_bt.items():
            occurring_os = self.get_opsys(ureport['releases'])

            if len(ureport['report']['bugs']) == 0 and "Red Hat Enterprise Linux" in occurring_os:
                for s in self.slave_dict[bthash]:
                    if s['probably_fixed'] is None:
                        continue

                    self.step6[bthash] = ureport

        # Step 7
        for bthash, ureport in self.master.master_bt.items():
            occurring_os = self.get_opsys(ureport['releases'])

            if len(ureport['report']['bugs']) == 0 and "CentOS" in occurring_os:
                for s in self.slave_dict[bthash]:
                    if s['probably_fixed'] is None:
                        continue

                    self.step7[bthash] = ureport

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

    def delete_hash(self, bt_hash):
        del(self.master.master_bt[bt_hash])
        del(self.slave_dict[bt_hash])

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

    @staticmethod
    def clear_cache():
        """
        Delete all cached file
        """
        files = os.listdir("cache")
        for f in files:
            os.unlink("cache/" + f)
            print "Delete cache cache/" + f

    @staticmethod
    def get_lastes_version(package_counts, component):
        last_version = ""
        for item in package_counts:
            if re.search("^" + component, item[0]):
                item[-1].sort(key=lambda x: x[0])
                last_version = item[-1][0][0]

        return last_version

    @staticmethod
    def get_bz_id(bug_url):
        return re.search('[0-9]*$', bug_url).group(0)

    @staticmethod
    def get_opsys(releases):
        os = []
        for r in releases:
            os.append(re.search('^[a-zA-Z ]*', r[0]).group(0).strip(" "))
        return os
