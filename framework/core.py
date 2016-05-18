import config
import sys
from pprint import pprint
import bugzilla
import re
import subprocess

class Core:

    master_hash = None
    slave_hash = None
    bz_bugs = dict()
    slave_dict = dict()

    # Data for separate steps
    step1 = dict()  # Bugzilla bugs with closed Fedora Bugzilla bugs
    step2 = dict()  # Bugzilla bugs probably fixed in RHEL
    step3 = dict()  # Bugzilla bugs probably fixed in fedora
    step4 = dict()  # Traces occurring on RHEL-${X} that are fixed in Fedora:

    output_message = ""

    def __init__(self, master, slave):
        self.master_hash = master
        self.slave_hash = slave

    def run(self):
        print "Start working with data"

        self.agregate_master_bthash()
        self.master_hash.download_ureport()  # Download ureports
        self.group_data_by_bt_hash()
        self.summarize_data()

        pprint(self.step1.keys())
        print "================"
        pprint(self.step2.keys())
        print "================"
        pprint(self.step3.keys())
        print "================"
        pprint(self.step3.keys())
        print "================"


        self.generate_output()
        sys.exit()

        print "All is done"
        print self.output_message
        # self.send_data_to_mail()
        sys.exit()

    def generate_output(self):

        # TODO Implement cache of bz bugs
        bz = bugzilla.Bugzilla(url="https://bugzilla.redhat.com/xmlrpc.cgi",
                               cookiefile=None)
        bz.login("phelia@redhat.com", "publicpassword01*")
        '''
        self.output_message += "RHEL-{0}.{1} Bugzilla bugs with closed Fedora Bugzilla " \
          "bugs:\n".format("7", "x")

        for key_hash, ureports in self.step1.items():
            known_bug_id = []

            master_report = self.master_hash.master_bt[key_hash]

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
        '''
        '''
        # generate output for step2
        for key_hash, ureport in self.step2.items():
            self.output_message += "\n Probably fixed Bugzilla bugs in RHEL-7\n"
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
                self.output_message += "\t- latest version : {0}".format(process.communicate()[0].split()[0])


        # generate output for step3
        self.output_message += "\n Probably fixed Bugzilla bugs in Fedora\n"
        for key_hash, ureport in self.step3.items():  # step 3 contain slave's reports
            master_report = self.master_hash.master_bt[key_hash]
            for master_bug in master_report['bugs']:
                if master_bug['type'] == 'BUGZILLA' and master_bug['status'] == 'NEW':
                    bz_bug = bz.getbug(master_bug['id'])

                    last_version = None
                    for item in ureport['package_counts']:
                        if re.search("^" + master_report['component'], item[0]):
                            item[-1].sort(key=lambda x: x[0])
                            last_version = item[-1][0][0]

            if ureport['probably_fixed'] and last_version:
                pfb = ureport['probably_fixed']['probable_fix_build']

                self.output_message += "* #{0} - [{1}] - {2}\n".format(master_bug['id'], master_report['component'],
                                                                       bz_bug.summary)
                self.output_message += "\t- last affected version: {0}\n".format(last_version)
                self.output_message += "\t- probably fixed in: {0}:{1}-{2}\n".format(pfb['epoch'], pfb['version'],
                                                                                     pfb['release'])
        '''
        print self.output_message

    def agregate_master_bthash(self):
        """
        Aggregate all unique bt_hash from slave servers and assign to
        master variable for downloading ureports from master
        """
        correct_bthashes = []
        for hashes in self.slave_hash.slave_bt.values():
            for slave_bthash in hashes.keys():
                if slave_bthash not in correct_bthashes:
                    correct_bthashes.append(slave_bthash)
        self.master_hash.master_bt = correct_bthashes

    def group_data_by_bt_hash(self):
        for master_bt, master_ureport in self.master_hash.master_bt.items():
            for server_name, slave_report in self.slave_hash.slave_bt.items():
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
                        if 'bugs' in self.master_hash.master_bt[bthash]:
                            for master_bug in self.master_hash.master_bt[bthash]['bugs']:
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
        for bthash, report in self.master_hash.master_bt.items():
            if bthash not in self.step1 and report['probably_fixed'] is not None and 'bugs' in report:
                for bug in report['bugs']:
                    if bug['type'] == 'BUGZILLA' and bug['status'] != 'CLOSED':
                        self.step2[bthash] = report

        # Step 3
        for bthash, report in self.master_hash.master_bt.items():
            if (bthash not in self.step1 and bthash not in self.step2) and 'bugs' in report:

                open_bugzilla = False

                for master_bug in report['bugs']:
                    if master_bug['type'] == 'BUGZILLA' and master_bug['status'] == 'NEW':
                        open_bugzilla = True

                if open_bugzilla:
                    for slave_report in self.slave_dict[bthash]:
                        if slave_report['probably_fixed'] is not None:
                            self.step3[bthash] = slave_report
                            '''
                            pprint(slave_report['probably_fixed'])
                            print bthash
                            exit()


                            latest_bug = None
                            if bug['type'] == 'BUGZILLA' and bug['status'] != 'CLOSED':
                                if latest_bug is None:
                                    latest_bug = bug
                                elif latest_bug['id'] < bug['id']:
                                    latest_bug = bug
                            '''
        # Step 4
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

    def delete_hash(self, bt_hash):
        del(self.master_hash.master_bt[bt_hash])
        del(self.slave_dict[bt_hash])
