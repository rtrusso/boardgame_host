#!/usr/bin/env python
from gevent import monkey
monkey.patch_all()

import argparse
from threading import Thread
from pkg_resources import iter_entry_points
from boardhost import host


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


client1 = host.Client(player_obj(board(), **player_kwargs),
                      args.address, args.port)
client2 = host.Client(player_obj(board(), **player_kwargs),
                      args.address, args.port)
server = host.Server(board(), args.address, args.port)

#print("starting server thread")
s_t = Thread(target=server.run)
s_t.start()
#print("starting client 1 thread")
c1_t = Thread(target=client1.run)
c1_t.start()
#print("starting client 2 thread")
c2_t = Thread(target=client2.run)
c2_t.start()

c1_t.join()
#print("c1_t returned")
c2_t.join()
#print("c2_t returned")
server.server.stop()
s_t.join()
#print("s_t returned")
