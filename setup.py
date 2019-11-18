from distutils.core import setup

setup(
    name='BoardHost',
    version='0.1-dev',
    author='Richard Russo',
    author_email='',
    packages=['boardhost'],
    scripts=['bin/board_host.py'],
    entry_points={
        'jrb_board.games': [],
        'jrb_board.players': ['human = boardhost.host:HumanPlayer',
                              'random = boardhost.host:RandomPlayer',
                              'random2 = boardhost.host:RandomPlayer'],
    },
    license='LICENSE',
    description="A generic board game host program.",
)
