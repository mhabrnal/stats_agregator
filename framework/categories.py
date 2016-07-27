import collections

from framework.acore import ACore
from framework.utils import *


class Categories(ACore):

    master = None
    slave = None
    bz = None
    bz_bugs = dict()
    components = dict()
    slave_dict = dict()

    already_processed = []
    # Data for separate steps
    step1 = dict()  # Bugzilla bugs with closed Fedora Bugzilla bugs
    step2 = dict()  # Bugzilla bugs probably fixed in RHEL
    step3 = dict()  # Bugzilla bugs probably fixed in fedora
    step4 = dict()  # # Resolved Fedora Bugzilla bugs appearing in RHEL-7
    step5 = dict()  # Traces occurring on CentOS-${X} that are fixed in Fedora:
    step6 = dict()  # Traces occurring on RHEL-${X} that are probably fixed in Fedora:
    step7 = dict()  # Traces occurring on CentOS-${X} that are probably fixed in Fedora:
    step8 = dict()  # Fedora Bugzilla bugs and CentOS bugs appearing in RHEL-7

    output_message = ""

    def __init__(self):
        super(Categories, self).__init__()

    def run(self):
        self.bz_bugs = load_binary_cache("bugzilla_bug.p")
        self.components = load_binary_cache("components.p")
        
        self.download_data()
        self.agregate_master_bthash()
        self.master.download_ureport()  # Download ureports
        self.group_data_by_bt_hash()
        self.summarize_data()
        self.sort_by_count()
        self.generate_output()

        save_binary_cache("bugzilla_bug.p", self.bz_bugs)
        save_binary_cache("components.p", self.components)

        for i in range(1, 9):
            step = getattr(self, "step" + str(i))
            print "Step {0} have {1} items".format(i, len(step))

        self.save_output_to_disk()

        # self.send_data_to_mail()

    def generate_output(self):
        self.output_step_1(self.step1)
        self.output_step_2(self.step2)
        self.output_step_3(self.step3)
        self.output_step_4(self.step4)
        self.output_step_5(self.step5)
        self.output_step_6(self.step6)
        self.output_step_7(self.step7)
        self.output_step_8(self.step8)

        print self.output_message

    def summarize_data(self):
        # Bugzilla bugs with closed Fedora Bugzilla bugs
        # Step 1
        for bthash, value in self.slave_dict.items():
            if bthash in self.already_processed:
                continue  # Data will be filled in next step

            for report in value:
                if 'bugs' not in report:
                    continue  # Don't iterate reports without bugs
                # Search bugzilla bug with closed fedora bugzilla bug
                for bug in report['bugs']:
                    if (bug['status'] == "CLOSED" and bug['resolution'] in ['ERRATA']) or bug['status'] in ['VERIFIED', 'RELEASE_PENDING']:
                        # Try to find bugs in master
                        if 'bugs' in self.master.master_bt[bthash]:
                            for master_bug in self.master.master_bt[bthash]['bugs']:
                                # what about ASSIGNED bugs? will those be included?
                                if master_bug['status'] in ['NEW', 'ASSIGNED'] and master_bug['type'] == 'BUGZILLA':
                                    atleast_one_new = True
                    else:
                        all_bugs_closed = False

                if all_bugs_closed and atleast_one_new:
                    self.step1[bthash] = self.slave_dict[bthash]
                    self.already_processed.append(bthash)

        # Bugzilla bugs probably fixed in RHEL
        # Step 2
        for bthash, report in self.master.master_bt.items():
            if bthash not in self.already_processed and report['probably_fixed'] is not None and 'bugs' in report:
                for bug in report['bugs']:
                    if bug['type'] == 'BUGZILLA' and (bug['status'] != 'CLOSED' and bug['status'] in ['NEW', 'ASSIGNED']):
                        first_occurrence = json_to_date(report['report']['first_occurrence'])
                        last_occurrence = json_to_date(report['report']['last_occurrence'])

                        avg_month_counter = int(
                            round(report['report']['count'] / get_mount_count(first_occurrence, last_occurrence)))

                        report['report']['avg_count'] = avg_month_counter

                        self.step2[bthash] = report
                        self.already_processed.append(bthash)

        # Bugzilla bugs probably fixed in fedora
        # Step 3
        for bthash, ureport in self.master.master_bt.items():
            if bthash in self.already_processed:
                continue

            if 'bugs' in ureport:
                pf = [r['probably_fixed'] for r in self.slave_dict[bthash] if r['probably_fixed'] is not None]
                if not pf:
                    continue

                bugs = [b for b in ureport['bugs'] if b['type'] == 'BUGZILLA']
                actual_bugs = []
                for b in bugs:
                    bz_b = self.get_bzbug(b['id'])
                    if bz_b.status in ('NEW', 'ASSIGNED'):
                        actual_bugs.append(b)

                if not actual_bugs:
                    continue

                self.step3[bthash] = ureport
                self.already_processed.append(bthash)

        # Traces occurring on RHEL-${X} that are fixed in Fedora:
        # Step 4
        for bthash, ureport in self.master.master_bt.items():
            if bthash in self.already_processed:
                continue

            occurring_os = get_opsys(ureport['releases'])

            if len(ureport['report']['bugs']) == 0 and "Red Hat Enterprise Linux" in occurring_os:
                for s in self.slave_dict[bthash]:
                    if 'bugs' not in s:
                        continue

                    bugs = [b for b in s['bugs'] if b['type'] == "BUGZILLA" and ((b['status'] in ['CLOSED'] and b['resolution'] in ['ERRATA', 'NEXTRELEASE', 'CURRENTRELEASE', 'RAWHIDE']) or (b['status'] in ['VERIFIED', 'RELEASE_PENDING']))]  # ON_QA, MODIFIED, VERIFIED
                    if not bugs:
                        continue

                    self.step4[bthash] = ureport
                    self.already_processed.append(bthash)

        # Traces occurring on CentOS-${X} that are fixed in Fedora:
        # Step 5
        for bthash, ureport in self.master.master_bt.items():
            if bthash in self.already_processed:
                continue

            occurring_os = get_opsys(ureport['releases'])
            if len(ureport['report']['bugs']) == 0 and "CentOS" in occurring_os:
                for s in self.slave_dict[bthash]:
                    if 'bugs' not in s:
                        continue

                    bugs = [b for b in s['bugs'] if
                            b['type'] == "MANTIS" and ((b['status'] in ['CLOSED'] and b['resolution'] in
                                                        ['ERRATA', 'NEXTRELEASE', 'CURRENTRELEASE', 'RAWHIDE'])
                                                       or (b['status'] in ['VERIFIED', 'RELEASE_PENDING']))]

                    if not bugs:
                        continue

                    self.step5[bthash] = ureport
                    self.already_processed.append(bthash)

        # Traces occurring on RHEL-${X} that are probably fixed in Fedora:
        # Step 6
        for bthash, ureport in self.master.master_bt.items():
            if bthash in self.already_processed:
                continue

            occurring_os = get_opsys(ureport['releases'])

            if len(ureport['report']['bugs']) == 0 and "Red Hat Enterprise Linux" in occurring_os and ureport['report']['count'] > 400:
                for s in self.slave_dict[bthash]:
                    if s['probably_fixed'] is None:
                        continue

                    self.step6[bthash] = ureport
                    self.already_processed.append(bthash)

        # Traces occurring on CentOS-${X} that are probably fixed in Fedora:
        # Step 7
        for bthash, ureport in self.master.master_bt.items():
            if bthash in self.already_processed:
                continue

            occurring_os = get_opsys(ureport['releases'])

            if len(ureport['report']['bugs']) == 0 and "CentOS" in occurring_os:
                for s in self.slave_dict[bthash]:
                    if s['probably_fixed'] is None:
                        continue

                    self.step7[bthash] = ureport
                    self.already_processed.append(bthash)

        # Traces occurring on RHEL-${X} with user details
        # Step 8
        for bthash, ureport in self.master.master_bt.items():
            if bthash in self.already_processed:
                continue

            if len(ureport['report']['bugs']) == 0 and ureport['report']['count'] > 0:
                for s in self.slave_dict[bthash]:
                    if 'bugs' not in s:
                        continue

                    valid = False
                    for bug in s['bugs']:
                        if bug['type'] != "BUGZILLA":
                            continue

                        bz_bug = self.get_bzbug(bug['id'])
                        if not bz_bug:
                            continue

                        if bz_bug.resolution not in ['EOL', 'NOTABUG', 'INSUFFICIENT_DATA', 'CANTFIX', 'WONTFIX',
                                                     'DEFFERRED', 'WORKSFORME', 'DUPLICATED', '']:
                            valid = True

                    if not valid:
                        continue

                    self.step8[bthash] = ureport

    def sort_by_count(self):
        for i in range(1, 9):
            if len(getattr(self, "step" + str(i))) > 0:
                step = getattr(self, "step" + str(i))
                step = collections.OrderedDict(
                    sorted(step.items(), key=lambda item: int(item[1]['avg_count_per_month']), reverse=True))
                setattr(self, "step" + str(i), step)
