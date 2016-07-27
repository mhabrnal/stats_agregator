import sys

if "--team" in sys.argv:
    # Divided by teams
    from framework.teams import Team
    team = Team()
    team.run()
else:
    # Default divided by categories
    from framework.categories import Categories
    core = Categories()
    core.run()
