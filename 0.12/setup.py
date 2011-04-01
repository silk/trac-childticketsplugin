from setuptools import find_packages, setup

# name can be any name.  This name will be used to create .egg file.
# name that is used in packages is the one that is used in the trac.ini file.
# use package name as entry_points
setup(
    name = 'Tracchildtickets',
    version = '2.1.1',
    packages = find_packages(),
    author = 'Mark Ryan',
    author_email = 'walnut.trac.hacks@gmail.com',
    description = 'Provides support for pseudo child-tickets and a visual reference to these within a parent ticket.',
    keywords = 'trac plugins ticket dependency childtickets',
    url = 'http://trac-hacks.org/wiki/ChildTicketsPlugin',
    install_requires = ['Trac>=0.12', 'Genshi>=0.5', 'Python>=2.4'],
    entry_points = """
        [trac.plugins]
        childtickets = childtickets
    """,
)
