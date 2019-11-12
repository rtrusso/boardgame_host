"""
A single-process host for the jrb_board.games and jrb_board.players interfaces.
"""
import json
import random
import socket
from random import choice
import gevent
import gevent.local
import gevent.queue
import gevent.server

# pylint: disable=missing-docstring
# pylint: disable=invalid-name
# pylint: disable=broad-except
# pylint: disable=fixme
# pylint: disable=no-self-use
# pylint: disable=too-many-instance-attributes

class Client:
    def __init__(self, player, addr=None, port=None):
        self.player = player
        self.running = False
        self.receiver = {'player': self.handle_player,
                         'decline': self.handle_decline,
                         'error': self.handle_error,
                         'illegal': self.handle_illegal,
                         'update': self.handle_update}

        self.addr = addr if addr is not None else '127.0.0.1'
        self.port = port if port is not None else 4242
        self.socket = None

    def run(self):
        #print("Connecting client")
        self.socket = socket.create_connection((self.addr, self.port))
        #print("client conected")
        self.running = True
        while self.running:
            message = ''
            while not message.endswith('\r\n'):
                #print("Client %s calling recv4096" %(self.player.player))
                message += str(self.socket.recv(4096), 'utf-8')
                #print("Client %s recv4096 returns '%s'" %(self.player.player, message))
            messages = message.rstrip().split('\r\n')
            for message in messages:
                data = json.loads(message)
                #print("Client recv message %s %s" %(self.player.player, data))
                if data['type'] not in self.receiver:
                    raise ValueError(
                        "Unexpected message from server: {0!r}".format(message))

                #print("Client %s dispatching ..." %(self.player.player))
                self.receiver[data['type']](data)
                #print("Client %s complete, next iter" %(self.player.player))

    def handle_player(self, data):
        player = data['message']
        #print("You are player #{0}.".format(player))
        self.player.player = player

    def handle_decline(self, data):
        print(data['message'])
        self.running = False

    def handle_error(self, data):
        print(data['message']) # FIXME: do something useful

    def handle_illegal(self, data):
        print(data['message']) # FIXME: do something useful

    def handle_update(self, data):
        #print("Client.handle_update %s %s" %(self.player.player, data))
        state = data['state']
        action = data.get('last_action', {}).get('action') or {}
        self.player.update(state)

        print(self.player.display(state, action))
        if data.get('winners') is not None:
            print(self.player.winner_message(data['winners']))
            self.running = False
        elif data['state']['player'] == self.player.player:
            self.send(self.player.get_action())

    def send(self, data):
        #print("Client.send %s %s" %(self.player.player, data))
        self.socket.sendall(bytes("{0}\r\n".format(json.dumps(data)), 'utf-8'))


class Server:
    def __init__(self, board, addr=None, port=None):
        self.board = board
        self.states = []
        self.local = gevent.local.local()
        self.server = None
        # player message queues
        self.players = dict((x, gevent.queue.Queue())
                            for x in range(1, self.board.num_players+1))
        # random player selection
        self.player_numbers = gevent.queue.JoinableQueue()

        self.addr = addr if addr is not None else '127.0.0.1'
        self.port = port if port is not None else 4242

    def game_reset(self):
        while True:
            # initialize the game state
            del self.states[:]
            state = self.board.starting_state()
            self.states.append(state)

            # update all players with the starting state
            state = self.board.to_json_state(state)
            # board = self.board.get_description()
            for x in range(1, self.board.num_players+1):
                self.players[x].put_nowait({
                    'type': 'update',
                    'board': None,  # board,
                    'state': state,
                })

            # randomize the player selection
            players = list(range(1, self.board.num_players+1))
            random.shuffle(players)
            for p in players:
                self.player_numbers.put_nowait(p)

            # block until all players have terminated
            self.player_numbers.join()

    def run(self):
        gevent.spawn(self.game_reset)
        self.server = gevent.server.StreamServer(listener=(self.addr, self.port),
                                                 handle=self.connection)
        #print("Starting server...")
        self.server.serve_forever()
        #print("Server stopped")

    def connection(self, sckt, _): # _ = address
        #print("connection:", sckt)
        self.local.socket = sckt
        if self.player_numbers.empty():
            self.send({
                'type': 'decline', 'message': "Game in progress."
            })
            sckt.close()
            return

        self.local.run = True
        self.local.player = self.player_numbers.get()
        self.send({'type': 'player', 'message': self.local.player})

        while self.local.run:
            #print("Server.connection waiting on dequeue %s" %(self.local.player))
            data = self.players[self.local.player].get()
            #print("Server.connection dequeue %s got %s" %(self.local.player, data))
            try:
                self.send(data)
                if data.get('winners') is not None:
                    self.local.run = False

                elif data.get('state', {}).get('player') == self.local.player:
                    message = ''
                    while not message.endswith('\r\n'):
                        message += str(sckt.recv(4096), 'utf-8')
                    messages = message.rstrip().split('\r\n')
                    self.parse(messages[0]) # FIXME: support for multiple messages
                                            #        or out-of-band requests
            except Exception as e:
                print(e)
                sckt.close()
                self.player_numbers.put_nowait(self.local.player)
                self.players[self.local.player].put_nowait(data)
                self.local.run = False
        self.player_numbers.task_done()

    def parse(self, msg):
        #print("Server.parse '%s' %s" %(self.local.player, msg))
        try:
            data = json.loads(msg)
            if data.get('type') != 'action':
                raise Exception
            self.handle_action(data)
        except Exception as e:
            print("Exception while parsing message: [{0}]".format(msg))
            print(e)
            self.players[self.local.player].put({
                'type': 'error', 'message': msg
            })

    def handle_action(self, data):
        #print("Server.handle_action %s" %(data))
        action = self.board.to_compact_action(data['message'])
        if not self.board.is_legal(self.states, action):
            self.players[self.local.player].put({
                'type': 'illegal', 'message': data['message'],
            })
            return

        self.states.append(self.board.next_state(self.states, action))
        state = self.board.to_json_state(self.states[-1])

        # TODO: provide a json object describing the board used
        data = {
            'type': 'update',
            'board': None,
            'state': state,
            'last_action': {
                'player': self.board.previous_player(self.states[-1]),
                'action': data['message'],
                'sequence': len(self.states),
            },
        }
        if self.board.is_ended(self.states):
            data['winners'] = self.board.win_values(self.states)
            data['points'] = self.board.points_values(self.states)

        for x in range(1, self.board.num_players+1):
            #print("players[%s].put(%s)" %(x, data))
            self.players[x].put(data)

    def send(self, data):
        #print("Server.send %s" %(data))
        self.local.socket.sendall(bytes("{0}\r\n".format(json.dumps(data)), 'utf-8'))


class HumanPlayer:
    def __init__(self, board):
        self.board = board
        self.player = None
        self.history = []

    def update(self, state):
        self.history.append(self.board.to_compact_state(state))

    def display(self, state, action):
        return self.board.display(state, action)

    def winner_message(self, winners):
        return self.board.winner_message(winners)

    def get_action(self):
        while True:
            notation = input("Please enter your action: ")
            action = self.board.from_notation(notation)
            if action is None:
                continue
            if self.board.is_legal(self.history, action):
                break
        return {
            'type': 'action',
            'message': self.board.to_json_action(action),
        }

class RandomPlayer:
    def __init__(self, board):
        self.board = board
        self.player = None
        self.history = []

    def update(self, state):
        self.history.append(self.board.to_compact_state(state))

    def display(self, state, action):
        return self.board.display(state, action)

    def winner_message(self, winners):
        return self.board.winner_message(winners)

    def get_action(self):
        legal = self.board.legal_actions(self.history)
        action = choice(legal)
        return {
            'type': 'action',
            'message': self.board.to_json_action(action),
        }
