import config
import sys
import pickle
import collections
import json
from pprint import pprint
import bugzilla
import re
import subprocess
import os
from datetime import datetime, timedelta
from framework.master import Master
from framework.slave import Slave
from framework.utils import *
from pkg_resources import parse_version

class Core:

    master = None
    slave = None
    bz = None
    bz_bugs = dict()
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
            self.clear_cache()
            self.master.download_all_hash()
            self.slave.download_ureports(self.master.master_bt)

    def run(self):

        self.download_data()
        self.agregate_master_bthash()
        self.master.download_ureport()  # Download ureports
        self.load_bugs()  # TODO REWRITE TO BINARY CACHE
        self.group_data_by_bt_hash()
        self.summarize_data()
        self.sort_by_count()
        self.generate_output()
        self.save_bugs()

        self.send_data_to_mail()

    def generate_output(self):
        if self.step1:
            self.output_message += "RHEL-{0} Bugzilla bugs with closed Fedora Bugzilla bugs:\n".format("7")

            for key_hash, ureports in self.step1.items():
                known_bug_id = []

                master_report = self.master.master_bt[key_hash]

                for master_bug in master_report['bugs']:
                    if master_bug['type'] == "BUGZILLA" and master_bug['status'] == 'NEW':

                        bz_bug = self.get_bzbug(master_bug['id'])

                        last_version = self.get_lastes_version(master_report['package_counts'], "tracker") # bz_bug.component
                        first_version = self.get_first_version(master_report['package_counts'], "tracker") # bz_bug.component

                        first_occurrence = self.json_to_date(master_report['report']['first_occurrence'])
                        last_occurrence = self.json_to_date(master_report['report']['last_occurrence'])

                        avg_month_counter = int(round(master_report['report']['count'] / self.get_mount_count(first_occurrence,
                                                                                                     last_occurrence)))

                        date_diff = self.date_diff(first_occurrence, last_occurrence)

                        if avg_month_counter <= 0:
                            continue

                        self.output_message += "* {0}: [{1}] - {2}\n".format(bz_bug.product, bz_bug.component,
                                                                             bz_bug.summary)

                        self.output_message += "\t- first / last affected RHEL version: {0} / {1}\n".format(first_version, last_version)
                        self.output_message += "\t- first / last RHEL occurrence:       {0} / {1} ({2})\n".format(first_occurrence.strftime("%Y-%m-%d"),
                                                                                     last_occurrence.strftime("%Y-%m-%d"),
                                                                                     date_diff)

                        self.output_message += "\t- RHEL total count:                   {0} (~{1}/month)\n".format(master_report['report']['count'],
                                                                           int(round(avg_month_counter)))

                        bugs = [bug for bug in master_report['bugs'] if bug['type'] == "BUGZILLA"
                                and bug['status'] in ['NEW']]

                        for b in bugs:
                            bz_bug = self.get_bzbug(b['id'])
                            self.output_message += self.bugzilla_url(bz_bug)

                for ureport in ureports:
                    for fedora_bug in ureport['bugs']:
                        if fedora_bug['status'] == 'CLOSED' and fedora_bug['id'] \
                                not in known_bug_id:
                            f_bug = self.get_bzbug(fedora_bug['id'])

                            known_bug_id.append(fedora_bug['id'])
                            self.output_message += "  {0}: #{1} - [{2}] - {3}\n".format(f_bug.product,
                                                                                        fedora_bug['id'],
                                                                                        f_bug.component,
                                                                                        f_bug.summary)
                            if f_bug.fixed_in:
                                self.output_message += "\t- fixed in:                           {0}\n".format(f_bug.fixed_in)
                            else:
                                self.output_message += "\t- fixed in:                           -\n"

                            self.output_message += self.bugzilla_url(f_bug)
        # generate output for step2
        if self.step2:
            self.output_message += "\nProbably fixed Bugzilla bugs in RHEL-7\n"
            for key_hash, ureport in self.step2.items():
                bugs = []
                for master_bug in ureport['bugs']:
                    if master_bug['type'] == 'BUGZILLA' and master_bug['status'] == 'NEW':
                        master_report = self.master.master_bt[key_hash]

                        bz_bug = self.get_bzbug(master_bug['id'])
                        bugs.append(master_bug)

                        last_version = self.get_lastes_version(master_report['package_counts'],
                                                               master_report['component'])
                        first_version = self.get_first_version(master_report['package_counts'],
                                                               master_report['component'])

                        first_occurrence = self.json_to_date(master_report['report']['first_occurrence'])
                        last_occurrence = self.json_to_date(master_report['report']['last_occurrence'])

                        date_diff = self.date_diff(first_occurrence, last_occurrence)

                        if master_report['avg_count_per_month'] <= 0:
                            continue

                        self.output_message += "* [{0}] - {1}\n".format(bz_bug.component, bz_bug.summary)

                        self.output_message += "\t- first / last affected RHEL version: {0} / {1}\n".format(
                            first_version, last_version)
                        self.output_message += "\t- first / last RHEL occurrence:       {0} / {1} ({2})\n".format(
                            first_occurrence.strftime("%Y-%m-%d"),
                            last_occurrence.strftime("%Y-%m-%d"),
                            date_diff)

                        self.output_message += "\t- RHEL total count:                   {0} (~{1}/month)\n".format(
                            master_report['report']['count'], master_report['avg_count_per_month'])

                if ureport['probably_fixed']:
                    pfb = ureport['probably_fixed']['probable_fix_build']

                    self.output_message += "\t- latest RHEL version:                {0}\n".format(self.get_rhel_latest_version(ureport['component']))

                    self.output_message += "\t- RHEL probably fixed in:             {0}:{1}-{2}\n".format(pfb['epoch'], pfb['version'],
                                                                                         pfb['release'])

                for b in bugs:
                    bz_bug = self.get_bzbug(b['id'])

                    self.output_message += self.bugzilla_url(bz_bug)

                self.output_message += "\n"

        # generate output for step3
        if self.step3:
            self.output_message += "\nRHEL-{0} Bugzilla bugs probably fixed in Fedora\n".format(7)
            for key_hash, value in self.step3.items():  # step 3 contain slave's reports

                master_report = self.master.master_bt[key_hash]

                last_version = self.get_lastes_version(master_report['package_counts'],
                                                       master_report['component'])
                first_version = self.get_first_version(master_report['package_counts'],
                                                       master_report['component'])

                first_occurrence = self.json_to_date(master_report['report']['first_occurrence'])
                last_occurrence = self.json_to_date(master_report['report']['last_occurrence'])

                date_diff = self.date_diff(first_occurrence, last_occurrence)

                if master_report['avg_count_per_month'] <= 0:
                    continue

                bugs = [b for b in master_report['bugs'] if b['type'] == 'BUGZILLA' and b['status'] in ('NEW', 'ASSIGNED')]

                correct_bug = True
                for b in bugs:
                    bz_bug = self.get_bzbug(b['id'])
                    if bz_bug.status not in ['NEW', 'ASSIGNED']:
                        correct_bug = False
                        continue

                    self.output_message += "*[{0}] - {1}\n".format(master_report['component'], bz_bug.summary)

                if correct_bug:
                    self.output_message += "\t- first / last affected RHEL version: {0} / {1}\n".format(
                        first_version, last_version)

                    self.output_message += "\t- first / last RHEL occurrence:       {0} / {1} ({2})\n".format(
                        first_occurrence.strftime("%Y-%m-%d"),
                        last_occurrence.strftime("%Y-%m-%d"),
                        date_diff)

                    self.output_message += "\t- RHEL total count:                   {0} (~{1}/month)\n".format(
                        master_report['report']['count'], master_report['avg_count_per_month'])

                    for b in bugs:
                        bz_bug = self.get_bzbug(b['id'])
                        self.output_message += self.bugzilla_url(bz_bug)

                    sr = [s for s in self.slave_dict[key_hash] if s['probably_fixed'] is not None]
                    for s in sr:
                        pfb = s['probably_fixed']['probable_fix_build']
                        self.output_message += "\t- Fedora probably fixed in:                  {0}:{1}-{2}\n".format(pfb['epoch'], pfb['version'],
                                                                                                                 pfb['release'])

                        self.output_message += "\t- {0}reports/{1}\n".format(s['source'], s['report']['id'])

                    self.output_message += "\n"

        # Resolved Fedora Bugzilla bugs appearing in RHEL-X
        if self.step4:
            self.output_message += "\nResolved Fedora Bugzilla bugs appearing in RHEL-{0}\n".format("7")
            for key_hash, ureport in self.step4.items():

                slave = []
                for sl in self.slave_dict[key_hash]:
                    for sb in sl['bugs']:
                        if sb['type'] == "BUGZILLA" and sb['resolution'] in ['ERRATA']:
                            slave.append(sl)

                if not slave:
                    continue

                master_report = self.master.master_bt[key_hash]

                last_version = self.get_lastes_version(master_report['package_counts'],
                                                       master_report['component'])

                first_version = self.get_first_version(master_report['package_counts'],
                                                       master_report['component'])

                first_occurrence = self.json_to_date(master_report['report']['first_occurrence'])
                last_occurrence = self.json_to_date(master_report['report']['last_occurrence'])

                date_diff = self.date_diff(first_occurrence, last_occurrence)

                if master_report['avg_count_per_month'] <= 0:
                    continue

                for s in slave:
                    for sb in s['bugs']:
                        bz_bug = self.get_bzbug(sb['id'])
                        self.output_message += "* [{0}] - {1}\n".format(master_report['report']['component'], bz_bug.summary)

                        self.output_message += "\t- first / last affected RHEL version: {0} / {1}\n".format(
                            first_version, last_version)

                        self.output_message += "\t- first / last RHEL occurrence:       {0} / {1} ({2})\n".format(
                            first_occurrence.strftime("%Y-%m-%d"),
                            last_occurrence.strftime("%Y-%m-%d"),
                            date_diff)

                        self.output_message += "\t- RHEL total count:                   {0} (~{1}/month)\n".format(
                            master_report['report']['count'], master_report['avg_count_per_month'])

                        self.output_message += "\t- https://faf-report.itos.redhat.com/reports/{0}\n".format(master_report['report']['id'])

                        self.output_message += "\t- Fedora fixed in:                     {0}\n".format(bz_bug.fixed_in)
                        last_version = self.get_lastes_version(ureport['package_counts'], master_report['component'])

                        self.output_message += self.bugzilla_url(bz_bug)
                        self.output_message += "\n"

        # Traces occurring on CentOS${X} that are fixed in Fedora:
        if self.step5:
            self.output_message += "\nTraces occurring on CentOS-{0} that are fixed in Fedora\n".format("7")
            for key_hash, ureport in self.step5.items():
                slave_bug = [sb for sb in self.slave_dict[key_hash][0]['bugs'] if
                             sb['type'] == "BUGZILLA" and sb['resolution'] in ['ERRATA']]
                if not slave_bug:
                    continue
                master_report = self.master.master_bt[key_hash]

                last_version = self.get_lastes_version(master_report['package_counts'],
                                                       master_report['component'])

                first_version = self.get_first_version(master_report['package_counts'],
                                                       master_report['component'])

                first_occurrence = self.json_to_date(master_report['report']['first_occurrence'])
                last_occurrence = self.json_to_date(master_report['report']['last_occurrence'])

                try:
                    avg_month_counter = int(round(master_report['report']['count'] / self.get_mount_count(first_occurrence,
                                                                                                          last_occurrence)))
                except:
                    continue

                if avg_month_counter <= 0:
                    continue

                for sb in slave_bug:
                    bz_bug = self.get_bzbug(sb['id'])
                    self.output_message += "* [{0}] - {1}\n".format(master_report['report']['component'], bz_bug.summary)

                    self.output_message += "\t- first / last affected RHEL version: {0} / {1}\n".format(
                        first_version, last_version)

                    self.output_message += "\t - fixed in: {0}\n".format(bz_bug.fixed_in)
                    last_version = self.get_lastes_version(ureport['package_counts'], master_report['component'])
                    self.output_message += "\t - last affected version: {0}\n".format(last_version)
                    self.output_message += self.bugzilla_url(bz_bug)

        # Traces occurring on RHEL-${X} that are probably fixed in Fedora:
        if self.step6:
            self.output_message += "\nTraces occurring on RHEL-{0} that are probably fixed in Fedora\n".format("7")
            for key_hash, ureport in self.step6.items():

                slave_pf = [spf for spf in self.slave_dict[key_hash] if spf['probably_fixed'] is not None]
                if not slave_pf:
                    continue

                master_report = self.master.master_bt[key_hash]
                last_version = self.get_lastes_version(master_report['package_counts'],
                                                       master_report['component'])

                first_version = self.get_first_version(master_report['package_counts'],
                                                       master_report['component'])

                first_occurrence = self.json_to_date(master_report['report']['first_occurrence'])
                last_occurrence = self.json_to_date(master_report['report']['last_occurrence'])

                date_diff = self.date_diff(first_occurrence, last_occurrence)

                avg_month_counter = int(round(master_report['report']['count'] / self.get_mount_count(first_occurrence,
                                                                                                      last_occurrence)))
                if avg_month_counter <= 0:
                    continue

                for spf in slave_pf:
                    pf = spf['probably_fixed']['probable_fix_build']

                    self.output_message += "* [{0}] - {1}\n".format(master_report['report']['component'], master_report['crash_function'])

                    self.output_message += "\t- first / last affected RHEL version: {0} / {1}\n".format(
                        first_version, last_version)

                    self.output_message += "\t- first / last RHEL occurrence:       {0} / {1} ({2})\n".format(
                        first_occurrence.strftime("%Y-%m-%d"),
                        last_occurrence.strftime("%Y-%m-%d"),
                        date_diff)

                    self.output_message += "\t- RHEL total count:                   {0} (~{1}/month)\n".format(
                        master_report['report']['count'],
                        int(round(avg_month_counter)))

                    self.output_message += "\t- latest RHEL version:                {0}\n".format(
                        self.get_rhel_latest_version(ureport['component']))

                    self.output_message += "\t- https://faf-report.itos.redhat.com/reports/{0}\n".format(
                        master_report['report']['id'])

                    self.output_message += "\t- Fedora probably fixed in:           {0}\n".format(pf['nvr'])

                    self.output_message += "\t- {0}reports/{1}\n\n".format(spf['source'], spf['report']['id'])

        # Traces occurring on CentOS-${0} that are probably fixed in Fedora
        if self.step7:
            self.output_message += "\nTraces occurring on CentOS-{0} that are probably fixed in Fedora\n".format("7")
            for key_hash, ureport in self.step7.items():

                slave_pf = [spf for spf in self.slave_dict[key_hash] if spf['probably_fixed'] is not None]
                if not slave_pf:
                    continue

                master_report = self.master.master_bt[key_hash]

                last_version = self.get_lastes_version(master_report['package_counts'],
                                                       master_report['component'])

                first_version = self.get_first_version(master_report['package_counts'],
                                                       master_report['component'])

                first_occurrence = self.json_to_date(master_report['report']['first_occurrence'])
                last_occurrence = self.json_to_date(master_report['report']['last_occurrence'])

                date_diff = self.date_diff(first_occurrence, last_occurrence)

                if master_report['avg_count_per_month'] <= 0:
                    continue

                for spf in slave_pf:
                    self.output_message += "* [{0}] - {1}\n".format(master_report['report']['component'], master_report['crash_function'])

                    self.output_message += "\t- first / last affected RHEL version: {0} / {1}\n".format(
                        first_version, last_version)

                    self.output_message += "\t- first / last RHEL occurrence:       {0} / {1} ({2})\n".format(
                        first_occurrence.strftime("%Y-%m-%d"),
                        last_occurrence.strftime("%Y-%m-%d"),
                        date_diff)

                    self.output_message += "\t- RHEL total count:                   {0} (~{1}/month)\n".format(
                        master_report['report']['count'], master_report['avg_count_per_month'])

                    self.output_message += "\t- latest RHEL version:                {0}\n".format(
                        self.get_rhel_latest_version(ureport['component']))

                    self.output_message += "\t- https://faf-report.itos.redhat.com/reports/{0}\n".format(
                        master_report['report']['id'])

                    pf = spf['probably_fixed']['probable_fix_build']

                    self.output_message += "\t- probably fixed in: {0}:{1}-{2}\n".format(pf['epoch'], pf['version'],
                                                                                          pf['release'])
                    last_version = self.get_lastes_version(ureport['package_counts'], master_report['component'])
                    self.output_message += "\t- last affected version: {0}\n".format(last_version)
                    self.output_message += "\t- {0}reports/{1}\n\n".format(self.master.url, ureport['report']['id'])# NA BZ

        # Fedora Bugzilla bugs and CentOS bugs appearing in RHEL-7
        if self.step8:
            self.output_message += "\nFedora Bugzilla bugs and CentOS bugs appearing in RHEL-{0}\n".format("7")
            for key_hash, ureport in self.step8.items():
                slave_pf = [spf for spf in self.slave_dict[key_hash]]  # if spf['probably_fixed'] is not None

                master_report = self.master.master_bt[key_hash]

                last_version = self.get_lastes_version(master_report['package_counts'],
                                                       master_report['component'])

                first_version = self.get_first_version(master_report['package_counts'],
                                                       master_report['component'])

                first_occurrence = self.json_to_date(master_report['report']['first_occurrence'])
                last_occurrence = self.json_to_date(master_report['report']['last_occurrence'])

                date_diff = self.date_diff(first_occurrence, last_occurrence)

                if master_report['avg_count_per_month'] <= 0:
                    continue

                self.output_message += "* [{0}] - {1}\n".format(master_report['report']['component'], master_report['crash_function'])

                self.output_message += "\t- first / last affected RHEL version: {0} / {1}\n".format(
                    first_version, last_version)

                self.output_message += "\t- first / last RHEL occurrence:       {0} / {1} ({2})\n".format(
                    first_occurrence.strftime("%Y-%m-%d"),
                    last_occurrence.strftime("%Y-%m-%d"),
                    date_diff)

                self.output_message += "\t- RHEL total count:                   {0} (~{1}/month)\n".format(
                    master_report['report']['count'], master_report['avg_count_per_month'])

                self.output_message += "\t- https://faf-report.itos.redhat.com/reports/{0}\n".format(
                    master_report['report']['id'])

                for spf in slave_pf:
                    last_slave_version = self.get_lastes_version(spf['package_counts'], master_report['component'])
                    first_slave_version = self.get_first_version(spf['package_counts'], master_report['component'])

                    first_slave_occurrence = self.json_to_date(spf['report']['first_occurrence'])
                    last_slave_occurrence = self.json_to_date(spf['report']['last_occurrence'])

                    slave_date_diff = self.date_diff(first_slave_occurrence, last_slave_occurrence)

                    self.output_message += "\t- first/last affected Fedora version: {0}/{1}\n".format(first_slave_version, last_slave_version)

                    self.output_message += "\t- first / last Fedora occurrence:     {0}/{1} ({2})\n".format(first_slave_occurrence.strftime("%Y-%m-%d"), last_slave_occurrence.strftime("%Y-%m-%d"), slave_date_diff)

                    self.output_message += "\t- Fedora total count:                 {0} (~{1}/month)\n".format(spf['report']['count'], spf['avg_count_per_month'])

                    for bug in spf['bugs']:
                        if bug['type'] == "BUGZILLA":
                            bz_bug = self.get_bzbug(bug['id'])
                            self.output_message += self.bugzilla_url(bz_bug)

                        elif bug['type'] == "MANTIS":
                            # TODO implement mantis api
                            pass
                self.output_message += "\n"

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
            if master_ureport['report']['component'] == "will-crash":
                self.delete_bthash(master_bt)
                continue
            for server_name, slave_report in self.slave.slave_bt.items():
                if master_bt in slave_report:
                    if master_bt not in self.slave_dict:
                        self.slave_dict[master_bt] = []
                    tmp_ureport = slave_report[master_bt]
                    tmp_ureport['source'] = config.SLAVE[server_name]
                    self.slave_dict[master_bt].append(tmp_ureport)

    def summarize_data(self):
        # Bugzilla bugs with closed Fedora Bugzilla bugs
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
                                if master_bug['status'] == "NEW" and master_bug['type'] == 'BUGZILLA':
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
                    if bug['type'] == 'BUGZILLA' and bug['status'] != 'CLOSED':
                        first_occurrence = self.json_to_date(report['report']['first_occurrence'])
                        last_occurrence = self.json_to_date(report['report']['last_occurrence'])

                        avg_month_counter = int(
                            round(report['report']['count'] / self.get_mount_count(first_occurrence, last_occurrence)))

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

                bugs = [b for b in ureport['bugs'] if b['type'] == 'BUGZILLA' and b['status'] in ('NEW', 'ASSIGNED')]

                if not bugs:
                    continue

                self.step3[bthash] = ureport
                self.already_processed.append(bthash)

        # Traces occurring on RHEL-${X} that are fixed in Fedora:
        # Step 4
        for bthash, ureport in self.master.master_bt.items():
            if bthash in self.already_processed:
                continue

            occurring_os = self.get_opsys(ureport['releases'])

            if len(ureport['report']['bugs']) == 0 and "Red Hat Enterprise Linux" in occurring_os:
                for s in self.slave_dict[bthash]:
                    if 'bugs' not in s:
                        continue

                    bugs = [b for b in s['bugs'] if b['type'] == "BUGZILLA" and b['status'] in ['CLOSED'] and b['resolution'] in ['ERRATA']]  # ON_QA, MODIFIED, VERIFIED
                    if not bugs:
                        continue

                    self.step4[bthash] = ureport
                    self.already_processed.append(bthash)

        # Traces occurring on CentOS-${X} that are fixed in Fedora:
        # Step 5
        for bthash, ureport in self.master.master_bt.items():
            if bthash in self.already_processed:
                continue

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
                    self.already_processed.append(bthash)

        # Traces occurring on RHEL-${X} that are probably fixed in Fedora:
        # Step 6
        for bthash, ureport in self.master.master_bt.items():
            if bthash in self.already_processed:
                continue

            occurring_os = self.get_opsys(ureport['releases'])

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

            occurring_os = self.get_opsys(ureport['releases'])

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

            if len(ureport['report']['bugs']) == 0 and ureport['report']['count'] > 200:
                for s in self.slave_dict[bthash]:
                    if 'bugs' not in s:
                        continue
                    '''
                    bugs = [b for b in s['bugs'] if
                            b['type'] == "BUGZILLA" and b['status'] in ['NEW']]
                    if not bugs:
                        continue
                    '''

                    self.step8[bthash] = ureport
                    # self.already_processed.append(bthash)

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
            bug = self.bz.getbug(id)
            self.bz_bugs[id] = bug
        return bug

    def load_bugs(self):
        if os.path.isfile("cache/bugtilla_bug"):
            with open("cache/bugzilla_bug", "rb") as f:
                try:
                    self.bz_bugs = pickle.load(f)
                except pickle.UnpicklingError as e:
                    print "{0}".format(e.message)
                    exit()

    def save_bugs(self):
        with open("cache/bugzilla_bug", "wb") as f:
            f.write(pickle.dumps(self.bz_bugs))

    def load_steps(self):
        all_correct = True
        for i in range(1, 9):
            bd = load_binary_cache("step_{0}.p".format(i))

            if bd is None:
                all_correct = False
            else:
                setattr(self, "step" + str(i), bd)

        if not all_correct:
            self.reset_steps()
            for i in range(1, 9):
                delete_cache_file("step_{0}.p".format(i))

        return all_correct

    def save_steps(self):
        for i in range(1, 9):
            step = getattr(self, "step" + str(i))
            save_binary_cache("step_{0}.p".format(i), step)

    def reset_steps(self):
        for i in range(1, 9):
            setattr(self, "step" + str(i), {})

    def sort_by_count(self):
        for i in range(1, 9):
            if len(getattr(self, "step" + str(i))) > 0:
                step = getattr(self, "step" + str(i))
                step = collections.OrderedDict(
                    sorted(step.items(), key=lambda item: int(item[1]['avg_count_per_month']), reverse=True))
                setattr(self, "step" + str(i), step)

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
                item[-1].sort(key=lambda x: parse_version(x[0]), reverse=True)
                last_version = item[-1][0][0]

        return last_version

    @staticmethod
    def get_first_version(package_counts, component):
        first_version = ""
        for item in package_counts:
            if re.search("^" + component, item[0]):
                item[-1].sort(key=lambda x: parse_version(x[0]))
                first_version = item[-1][0][0]

        return first_version

    @staticmethod
    def get_bz_id(bug_url):
        return re.search('[0-9]*$', bug_url).group(0)

    @staticmethod
    def get_opsys(releases):
        os = []
        for r in releases:
            os.append(re.search('^[a-zA-Z ]*', r[0]).group(0).strip(" "))
        return os

    # Find a way how to get name from oops log
    def get_name_from_oops(oops):
        pass

    @staticmethod
    def json_to_date(json_date):
        try:
            d = datetime.strptime(json_date, '%Y-%m-%dT%H:%M:%S.%f')
        except:
            try:
                d = datetime.strptime(json_date, '%Y-%m-%dT%H:%M:%S')
            except ValueError:
                print "time data does not match allowed format."

        return d


    @staticmethod
    def date_diff(first, last):
        diff = last - first

        year = diff.days / 365
        months = round((diff.days / 30.4) - (year * 12))

        spell_m = "month"
        if months > 1:
            spell_m = "months"

        spell_y = "year"
        if year > 1:
            spell_y = "years"

        if year > 0 and months > 0:
            return "~ {0} {1} {2} {3}".format(year, spell_y, str(int(months)), spell_m)
        elif year > 0:
            return "~ {0} {1}".format(year, spell_y)
        elif months > 0:
            return "~ {0} {1}".format(str(int(months)), spell_m)
        else:
            return "~1 month"

    @staticmethod
    def get_mount_count(first, last):
        diff = last - first
        r_d = diff.days / 30.4
        if r_d < 1:
            return 1
        return round(r_d)

    @staticmethod
    def get_rhel_latest_version(component):

        bash_command = "brew latest-build rhel-7.3 {0} --quiet".format(component)
        process = subprocess.Popen(bash_command.split(), stdout=subprocess.PIPE)

        return process.communicate()[0].split()[0]

    @staticmethod
    def bugzilla_url(bz_bug):
        status = bz_bug.status
        if bz_bug.status == "CLOSED":
            status += " {0}".format(bz_bug.resolution)

        return "\t- https://bugzilla.redhat.com/{0} - {1}\n".format(bz_bug.id, status)

    def delete_bthash(self, bt_hash):
        del(self.master.master_bt[bt_hash])
