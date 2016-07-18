import sys

if "--team" in sys.argv:
    # divided by teams
    from framework.teams import Team
    team = Team()
    team.run()
else:
    # Defaulf didided by categories
    from framework.categories import Categories
    core = Categories()
    core.run()
