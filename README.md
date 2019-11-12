boardgame-host
==============

A host console program for pluggable board game and player
implementations. Tested with Python 3.7.2.

Game implementations:
- [go](https://github.com/rtrusso)
- [ultimate tic-tac-toe](https://github.com/rtrusso/ultimate_tictactoe)
- [reversi](https://github.com/jbradberry/reversi)
- [connect four](https://github.com/jbradberry/connect-four)

Player implementations:
- human, random: built-in
- [mcts](https://github.com/rtrusso/mcts)

Getting Started
---------------

To set up your local environment you should create a virtualenv and
install everything into it.

    $ python -m virtualenv boardgames

Pip install this repo, either from a local copy:

    $ pip install -e boardgame_host

or from github:

    $ pip install git+https://github.com/rtrusso/boardgame_host

Run the tool with the go implementation and the random player:

    $ board_host.py go random


Planned Improvements
--------------------

- Make this more efficient, without sockets and http in the middle
- Experiments with many test runs
- Aggregate data for win-loss, performance, etc.
