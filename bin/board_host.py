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

import sys
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
    parser.add_argument('player', choices=sorted(player_plugins), nargs='+')
    parser.add_argument('address', nargs='?')
    parser.add_argument('port', nargs='?', type=int)
    parser.add_argument('-e', '--extra', action='append')

    args = parser.parse_args()

    board = board_plugins[args.game]
    brd = board()
    num_players = brd.num_players
    player_spec = []
    for p in args.player:
        player_spec.append(p)

    print("game:      %s" %(args.game))
    print("# players: %s" %(num_players))

    if len(player_spec) > num_players:
        print("too many players specified for game")
        sys.exit(1)

    while len(player_spec) < num_players:
        player_spec.append(player_spec[-1])

    print("player:    %s" %(player_spec))
    player_kwargs = dict(arg.split('=') for arg in args.extra or ())

    clients = []
    player_spec_len = len(player_spec)
    transcript = True
    for index in range(1, num_players+1):
        player_index = index % player_spec_len
        player_class_name = player_spec[player_index]
        player_obj = player_plugins[player_class_name]
        clients.append(host.Client(player=player_obj(board(), **player_kwargs),
                                   addr=args.address, port=args.port,
                                   transcript=transcript))
        transcript = False

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
    sys.exit(0)

main()
