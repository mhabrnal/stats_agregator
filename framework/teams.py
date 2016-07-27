import collections

from framework.acore import ACore
from framework.utils import *


class Team(ACore):

    master = None
    slave = None
    bz = None
    bz_bugs = dict()
    teams = dict()
    team_data = dict()
    components = dict()

    output_message = ""

    def __init__(self):
        super(Team, self).__init__()

    def run(self):
        self.bz_bugs = load_binary_cache("bugzilla_bug.p")
        self.components = load_binary_cache("components.p")
        self.teams = load_binary_cache("teams.p")
        
        self.download_data()
        self.agregate_master_bthash()
        self.master.download_ureport()  # Download ureports
        self.group_data_by_bt_hash()
        self.summarize_data()
        self.sort_by_count()
        self.generate_output()

        save_binary_cache("bugzilla_bug.p", self.bz_bugs)
        save_binary_cache("components.p", self.components)
        save_binary_cache("teams.p", self.teams)

        self.save_output_to_disk()

        # self.send_data_to_mail()

    def generate_output(self):
        for team_name, team_steps in self.team_data.items():
            if team_name == "UNKNOWN":
                continue

            self.output_message += "{0}\n\n".format(team_name)

            self.output_step_1(team_steps['step1'])
            self.output_step_2(team_steps['step2'])
            self.output_step_3(team_steps['step3'])
            self.output_step_4(team_steps['step4'])
            self.output_step_5(team_steps['step5'])
            self.output_step_6(team_steps['step6'])
            self.output_step_7(team_steps['step7'])
            self.output_step_8(team_steps['step8'])

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
                    master = self.master.master_bt[bthash]

                    team_name = self.create_team(master['component'], master['maintainer_contanct'])

                    self.team_data[team_name]['step1'][bthash] = self.slave_dict[bthash]
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

                        team_name = self.create_team(report['component'], report['maintainer_contanct'])

                        self.team_data[team_name]['step2'][bthash] = report

        # Bugzilla bugs probably fixed in fedora
        # Step 3
        for bthash, report in self.master.master_bt.items():
            if bthash in self.already_processed:
                continue

            if 'bugs' in report:
                pf = [r['probably_fixed'] for r in self.slave_dict[bthash] if r['probably_fixed'] is not None]
                if not pf:
                    continue

                bugs = [b for b in report['bugs'] if b['type'] == 'BUGZILLA']
                actual_bugs = []
                for b in bugs:
                    bz_b = self.get_bzbug(b['id'])
                    if bz_b.status in ('NEW', 'ASSIGNED'):
                        actual_bugs.append(b)

                if not actual_bugs:
                    continue

                team_name = self.create_team(report['component'], report['maintainer_contanct'])

                self.team_data[team_name]['step3'][bthash] = report
                self.already_processed.append(bthash)

        # Traces occurring on RHEL-${X} that are fixed in Fedora:
        # Step 4
        for bthash, report in self.master.master_bt.items():
            if bthash in self.already_processed:
                continue

            occurring_os = get_opsys(report['releases'])

            if len(report['report']['bugs']) == 0 and "Red Hat Enterprise Linux" in occurring_os:
                for s in self.slave_dict[bthash]:
                    if 'bugs' not in s:
                        continue

                    bugs = [b for b in s['bugs'] if b['type'] == "BUGZILLA" and ((b['status'] in ['CLOSED'] and b['resolution'] in ['ERRATA', 'NEXTRELEASE', 'CURRENTRELEASE', 'RAWHIDE']) or (b['status'] in ['VERIFIED', 'RELEASE_PENDING']))]  # ON_QA, MODIFIED, VERIFIED
                    if not bugs:
                        continue

                    team_name = self.create_team(report['component'], report['maintainer_contanct'])

                    self.team_data[team_name]['step4'][bthash] = report
                    self.already_processed.append(bthash)

        # Traces occurring on CentOS-${X} that are fixed in Fedora:
        # Step 5
        for bthash, report in self.master.master_bt.items():
            if bthash in self.already_processed:
                continue

            occurring_os = get_opsys(report['releases'])
            if len(report['report']['bugs']) == 0 and "CentOS" in occurring_os:
                for s in self.slave_dict[bthash]:
                    if 'bugs' not in s:
                        continue

                    bugs = [b for b in s['bugs'] if
                            b['type'] == "MANTIS" and ((b['status'] in ['CLOSED'] and b['resolution'] in
                                                        ['ERRATA', 'NEXTRELEASE', 'CURRENTRELEASE', 'RAWHIDE'])
                                                       or (b['status'] in ['VERIFIED', 'RELEASE_PENDING']))]

                    if not bugs:
                        continue

                    team_name = self.create_team(report['component'], report['maintainer_contanct'])

                    self.team_data[team_name]['step5'][bthash] = report
                    self.already_processed.append(bthash)

        # Traces occurring on RHEL-${X} that are probably fixed in Fedora:
        # Step 6
        for bthash, report in self.master.master_bt.items():
            if bthash in self.already_processed:
                continue

            occurring_os = get_opsys(report['releases'])

            if len(report['report']['bugs']) == 0 and "Red Hat Enterprise Linux" in occurring_os and report['report']['count'] > 400:
                for s in self.slave_dict[bthash]:
                    if s['probably_fixed'] is None:
                        continue

                    team_name = self.create_team(report['component'], report['maintainer_contanct'])

                    self.team_data[team_name]['step6'][bthash] = report
                    self.already_processed.append(bthash)

        # Traces occurring on CentOS-${X} that are probably fixed in Fedora:
        # Step 7
        for bthash, report in self.master.master_bt.items():
            if bthash in self.already_processed:
                continue

            occurring_os = get_opsys(report['releases'])

            if len(report['report']['bugs']) == 0 and "CentOS" in occurring_os:
                for s in self.slave_dict[bthash]:
                    if s['probably_fixed'] is None:
                        continue

                    team_name = self.create_team(report['component'], report['maintainer_contanct'])

                    self.team_data[team_name]['step7'][bthash] = report
                    self.already_processed.append(bthash)

        # Traces occurring on RHEL-${X} with user details
        # Step 8
        for bthash, report in self.master.master_bt.items():
            if bthash in self.already_processed:
                continue

            if len(report['report']['bugs']) == 0 and report['report']['count'] > 0:
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

                    self.team_data[team_name]['step8'][bthash] = report

    def create_team(self, component_name, user):
        team_key = str('{0}:{1}'.format(component_name, user))

        if team_key not in self.teams:
            team = watson_api(component_name, user)
            team = team['subsystem']
            if team == 'UNKNOWN':  # This team probably doesn't belongs to RHEL
                print component_name

            self.teams[team_key] = team
        else:
            team = self.teams[team_key]

        if team not in self.team_data:
            self.team_data[team] = dict()

            for x in range(1, 9):
                self.team_data[team]['step{0}'.format(x)] = dict()

        return team

    def sort_by_count(self):
        for team_steps in self.team_data.values():
            for i in range(1, 9):
                if len(team_steps['step{0}'.format(i)]) > 0:
                    step = collections.OrderedDict(
                        sorted(team_steps['step{0}'.format(i)].items(), key=lambda item: int(item[1]['avg_count_per_month']), reverse=True))

                    team_steps['step{0}'.format(i)] = step
