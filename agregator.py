import argparse
import sys

parser = argparse.ArgumentParser(description="FAF Statistic agregator")

parser.add_argument('--team', action='store_true', help='Group report by team')
parser.add_argument('--category', action='store_true', help='Group report by category')
parser.add_argument('--sendmail', action='store_true', help='Send email to all recipient')

args = parser.parse_args()

if args.team:
    # Divided by teams
    from framework.teams import Team
    core = Team()
    core.run()
elif args.category:
    # Default divided by categories
    from framework.categories import Categories
    core = Categories()
    core.run()
else:
    print "You have to specify grouping parameter"
    sys.exit()

if args.sendmail:
    core.send_data_to_mail()
