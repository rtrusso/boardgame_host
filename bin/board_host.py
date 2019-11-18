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
import time
import argparse
from threading import Thread
from pkg_resources import iter_entry_points
from boardhost import host
from tqdm import tqdm

def emit_stats(elapsed_seconds, res):
    """print out stats for the game runs. res is an array of dictionaries
    created by the server for each win.

    """
    count = 0
    hist = dict()
    for r in res:
        count = count + 1
        key = (r['message'], r['class_name'])
        if key in hist:
            hist[key] = hist[key] + 1
        else:
            hist[key] = 1

    sorted_hist = sorted((wins, key) for key, wins in hist.items())
    for obj in sorted_hist:
        (wins, key) = obj
        c = wins
        p = round((c / (1.0 * count)) * 100.0, 2)
        (msg, class_name) = key
        print("[%s/%s] %s%s %s '%s'" %(c, count, p, '%', class_name, msg))
    print("of %s game(s) played" %(count))
    print("%ss elapsed" %(round(elapsed_seconds, 2)))
    games_per_second = count / (1.0 * elapsed_seconds)
    if games_per_second < 1:
        seconds_per_game = elapsed_seconds / count
        print("%s s/game" %(round(seconds_per_game, 2)))
    else:
        print("%s games/s" %(round(games_per_second, 2)))

def main():
    """main entry point from the console.

    """
    # pylint: disable=too-many-statements
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
    parser.add_argument('--iterations', '-i', type=int)
    parser.add_argument('--transcript', '-t', action='store_true')
    parser.add_argument('-e', '--extra', action='append')

    args = parser.parse_args()

    board = board_plugins[args.game]
    brd = board()
    num_players = brd.num_players
    player_spec = []
    for p in args.player:
        player_spec.append(p)

    print("game:        %s" %(args.game))
    print("# player(s): %s" %(num_players))

    if len(player_spec) > num_players:
        print("too many players specified for game")
        sys.exit(1)

    player_spec_len = len(player_spec)
    player_classes = []
    for index in range(1, num_players+1):
        player_index = (index-1) % player_spec_len
        player_class_name = player_spec[player_index]
        player_classes.append(player_class_name)

    print("player(s):   %s" %(player_classes))
    player_kwargs = dict(arg.split('=') for arg in args.extra or ())

    n = 1
    if args.iterations is not None:
        n = args.iterations

    server_transcript = args.transcript or (args.iterations is None)
    server = host.Server(board=board(),
                         player_classes=player_classes,
                         transcript=server_transcript,
                         addr=args.address,
                         port=args.port)

    s_t = Thread(target=server.run)
    s_t.start()

    start_time = time.perf_counter()
    for game_index in tqdm(range(0, n), disable=args.transcript, ascii=True):
        if args.transcript:
            print("round %s" %(game_index+1))
        clients = []
        game_transcript = args.transcript
        for index in range(1, num_players+1):
            player_class_name = player_classes[index-1]
            player_obj = player_plugins[player_class_name]
            clients.append(host.Client(player=player_obj(board(), **player_kwargs),
                                       player_class=player_class_name,
                                       addr=args.address, port=args.port,
                                       transcript=game_transcript))
            game_transcript = False


        client_threads = []
        for c in clients:
            client_threads.append(Thread(target=c.run))

        for t in client_threads:
            t.start()

        for t in client_threads:
            t.join()

    end_time = time.perf_counter()
    server.server.stop()
    s_t.join()

    if n > 1:
        q = server.results
        res = []
        while q.qsize() > 0:
            res.append(q.get())
        emit_stats(end_time - start_time, res)

    sys.exit(0)

main()
