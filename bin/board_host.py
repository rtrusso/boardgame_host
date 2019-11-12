#!/usr/bin/env python
"""
main script used to execute the boardgame host from the command line.
"""
# pylint: disable=wrong-import-position
# pylint: disable=wrong-import-order
# pylint: disable=invalid-name
# pylint: disable=too-many-locals
from gevent import monkey
monkey.patch_all()

import argparse
from threading import Thread
from pkg_resources import iter_entry_points
from boardhost import host

def main():
    """
    main entry point from the console.
    """
    board_plugins = dict(
        (ep.name, ep.load())
        for ep in iter_entry_points('jrb_board.games')
    )

    player_plugins = dict(
        (ep.name, ep.load())
        for ep in iter_entry_points('jrb_board.players')
    )

    parser = argparse.ArgumentParser(
        description="Play a boardgame using a specified player type.")
    parser.add_argument('game', choices=sorted(board_plugins))
    parser.add_argument('player', choices=sorted(player_plugins))
    parser.add_argument('address', nargs='?')
    parser.add_argument('port', nargs='?', type=int)
    parser.add_argument('-e', '--extra', action='append')

    args = parser.parse_args()

    print("game: %s" %(args.game))
    print("player: %s" %(args.player))

    board = board_plugins[args.game]
    player_obj = player_plugins[args.player]
    player_kwargs = dict(arg.split('=') for arg in args.extra or ())

    brd = board()
    num_players = brd.num_players
    clients = []
    for _ in range(1, num_players+1):
        clients.append(host.Client(player_obj(board(), **player_kwargs),
                                   args.address, args.port))

    server = host.Server(board(), args.address, args.port)

    s_t = Thread(target=server.run)
    s_t.start()

    client_threads = []
    for c in clients:
        client_threads.append(Thread(target=c.run))

    for t in client_threads:
        t.start()

    for t in client_threads:
        t.join()

    server.server.stop()
    s_t.join()

main()
