import config
import sys
from pprint import pprint
import bugzilla

class Core:

    master_hash = None
    slave_hash = None
    bz_bugs = dict()
    slave_dict = dict()

    # Data for separate steps
    step1 = dict()  # Bugzilla bugs with closed Fedora Bugzilla bugs

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
        self.generate_output()


        print "All is done"
        print self.output_message
        self.send_data_to_mail()
        sys.exit()

    def generate_output(self):
        # TODO Implement cache of bz bugs
        bz = bugzilla.Bugzilla(url="https://bugzilla.redhat.com/xmlrpc.cgi", 
                               cookiefile=None)
        bz.login("phelia@redhat.com", "publicpassword01*")

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
                        if item[0] == 'tracker':
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

    def summarize_data(self):
        for bthash, value in self.slave_dict.items():
            if bthash in self.step1:
                continue  # Data will be filled in next step

            for report in value:
                if 'bugs' not in report:
                    continue  # Don't iterate reports without bugs

                for bug in report['bugs']:
                    if bug['resolution'] in config.step_1:
                        # Try to find bugs in master
                        if 'bugs' in self.master_hash.master_bt[bthash]:
                            for master_bug in self.master_hash.master_bt[bthash]['bugs']:
                                if master_bug['status'] == "NEW":
                                    atleast_one_new = True

                                    # TODO DELETE THIS LINE
                                    self.step1[bthash] = self.slave_dict[bthash]
                    else:
                        all_bugs_closed = False

                if all_bugs_closed and atleast_one_new:
                    self.step1[bthash] = self.slave_dict[bthash]

    def send_data_to_mail(self):
        import smtplib
        from email.mime.text import MIMEText

        msg = MIMEText(self.output_message)

        msg['Subjet'] = "ABRT Mail stats"
        msg['From'] = "phelia@redhat.com"
        msg['To'] = "phelia@redhat.com"

        s = smtplib.SMTP('localhost')
        s.sendmail('phelia@redhat.com', 'phelia@redhat.com', msg.as_string())
        s.quit()
