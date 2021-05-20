# CITS3002 2021 Assignment      Dylan Fellows 22731134


import socket
import sys
import tiles
from time import sleep
import random
from threading import Thread

#When set to None, a timer will start once 2 clients have connected, 
#Once its finished, we will know the max amount of players
#The timer didnt work well with the given marking program but i was told the final one will be more forgiving
#Please set the max players to 2, 3, or 4 if the program doesnt work with the timer
maximum_players = None

#Holds how many clients are connected
clients_connected = 0
#Holds the idnum of all connected players
connected_players = []
#holds players: idnum, name, address, connection respectfully 
players = [] 



#Welcomes every client to the game and puts them into arrays for later use
def client_handler(connection, address):

    global clients_connected
    print(clients_connected, " Clients have connetect")
    host, port = address
    name = '{}:{}'.format(host, port)

    if len(connected_players) == 0:
        idnum = 0
    else:
        idnum = connected_players[-1] + 1
    connected_players.append(idnum)
    
    players.append([idnum, name, address, connection])
    
    connection.send(tiles.MessageWelcome(idnum).pack())
    

#Stars each game and loops with a 5 second delay for players to think about their mistakes
def game_loop():
    while True:
        print("New game commencing")
        start_game(setup_game())
        print("New game commencing in 1s")
        sleep(5)

#Randomly chooses the players, player order and adds them to the game
def setup_game():
    print("game setting up")

    if len(players) > 4: #finds how many players will be participating 
        max_players = 4
    else:
        max_players = len(players) 

    #adds everone into a spectator list
    spectators = []
    for k in players:
        spectators.append(k)

    #chooses a random spectator to play, them delets them form the spectator list
    active_players = []
    for k in range(max_players):
        random_spectator = random.randint(0, len(spectators)-1)
        active_players.append(spectators[random_spectator])
        spectators.pop(random_spectator)

    #Initialise player order
    player_order = []
    for k in range (0, max_players):
        player_order.append(None)

    #Fills player order randomly
    for player in active_players:
        randon_position = random.randint(0, max_players-1)
        while player_order[randon_position] != None:
            randon_position = random.randint(0, max_players-1)
        player_order[randon_position] = player[0]


    #populates the live_idnums array
    live_idnums = []
    for player in active_players:
        live_idnums.append(player[0])

    #sent to all clients, that a player has joined
    for joiner in players:
        for player in players:
            print("sending Join to: ", player[0])
            player[3].send(tiles.MessagePlayerJoined(joiner[1], joiner[0]).pack())

    
    #notify all clients that the game is starting
    for player in players:
        print("sending start to: ", player[0])
        player[3].send(tiles.MessageGameStart().pack())

    #generate all clients a hand
    for player in active_players:
        for _ in range(tiles.HAND_SIZE):
            tileid = tiles.get_random_tileid()
            player[3].send(tiles.MessageAddTileToHand(tileid).pack())
    
    return [live_idnums, player_order]

#Finds out who is the next player to go and makes them the current player
def iterate_players(player_order, current_player, current_player_index):
    if current_player_index < len(player_order) - 1:
        current_player = player_order[current_player_index + 1]
    else:
        current_player = player_order[0]

    return current_player


#Starts teh game!!
def start_game(setup_data):

    live_idnums = setup_data[0]     #returned form setup_game()     
    player_order = setup_data[1]    #returned form setup_game()

    print("game running")
    
    current_player = player_order[0]
    print("Current player is now: ", current_player)


    for player in players:
        print("telling ", player[0]," that the current player is ", current_player)
        player[3].send(tiles.MessagePlayerTurn(current_player).pack())
    
    board = tiles.Board()

    buffer = bytearray()
    
    while True: #Main gameplay loop
        print("--starting loop--")
        current_player_index = player_order.index(current_player)
        dead = False

        print("current player; ", current_player)

        chunk = players[current_player][3].recv(4096)     

        if not chunk:
            print('client {} disconnected'.format(players[current_player][2]))
            return

        buffer.extend(chunk)
    
        while True:
            msg, consumed = tiles.read_message_from_bytearray(buffer)
            if not consumed:
                break
            buffer = buffer[consumed:]

            print('received message {}'.format(msg))
    
            # sent by the player to put a tile onto the board (in all turns except           
            # their second)
            if isinstance(msg, tiles.MessagePlaceTile):
                if board.set_tile(msg.x, msg.y, msg.tileid, msg.rotation, msg.idnum):

                    # notify all clients that placement was successful
                    for player in players:
                            player[3].send(msg.pack())

                    # check for token movement
                    positionupdates, eliminated = board.do_player_movement(live_idnums)
                    
                    
                    for msg in positionupdates:
                        for player in players:
                            player[3].send(msg.pack())


                    #This part isnt very efficient, but it checks all players if they are eliminated
                    #Then notifies the other players of their elimination
                    for l_id in live_idnums:    
                        if l_id in eliminated:
                            print(l_id, " Has been eliminated")
                            live_idnums.remove(l_id)
                            player_order.remove(l_id)
                            for player in players:
                                player[3].send(tiles.MessagePlayerEliminated(l_id).pack())

                            if current_player in eliminated:
                                dead = True

                            if len(live_idnums) == 1:   #1 player left, game over
                                return
                            

                    # pickup a new tile
                    tileid = tiles.get_random_tileid()
                    players[current_player][3].send(tiles.MessageAddTileToHand(tileid).pack())
                    
                    
          
                    if len(live_idnums) <= 1: #1 player left, game over
                        return

                    if len(player_order) < 2: #1 player left, game over
                        return

                    #This part is very inefficient, finds out where the current player is in the player_order array
                    if not dead:
                        current_player_index = player_order.index(current_player)
                    else:
                        if current_player_index > 0:
                            current_player_index -= 1
                        else:
                            current_player_index = len(player_order)-1

                    #Then makes the 'current player' the next player is the play order
                    current_player = iterate_players(player_order, current_player, current_player_index)
                    count = 0
                    while current_player in eliminated:   #if this loops, it means there has been a draw so a winner is picked
                        count += 1
                        if count > 10:
                            for player in players:
                                player[3].send(tiles.MessagePlayerEliminated(player_order[0]).pack())
                            return
                        current_player = iterate_players(player_order, current_player, current_player_index)
                        
                  
                    #Notifies all clients of whos turn it is
                    for player in players:
                        player[3].send(tiles.MessagePlayerTurn(current_player).pack())

        # sent by the player in the second turn, to choose their token's
            elif isinstance(msg, tiles.MessageMoveToken):
                if not board.have_player_position(msg.idnum):
                    if board.set_player_start_position(msg.idnum, msg.x, msg.y, msg.position):
                        # check for token movement
                        positionupdates, eliminated = board.do_player_movement(live_idnums)

                        for msg in positionupdates:
                            for player in players:
                                player[3].send(msg.pack())

                        #This part isnt very efficient, but it checks all players if they are eliminated
                         #Then notifies the other players of their elimination
                        for l_id in live_idnums:    
                            if l_id in eliminated:
                                live_idnums.remove(l_id)
                                player_order.remove(l_id)
                                for player in players:
                                    player[3].send(tiles.MessagePlayerEliminated(l_id).pack())

                                if current_player in eliminated:
                                    dead = True

                                if len(live_idnums) == 1: #1 player left, game over
                                    return
                
                       
                        if len(live_idnums) == 1: #1 player left, game over
                            return

                        if len(player_order) < 2: #1 player left, game over
                            return

                        #This part is very inefficient, finds out where the current player is in the player_order array
                        if not dead:
                            current_player_index = player_order.index(current_player)
                        else:
                            if current_player_index > 0:
                                current_player_index -= 1
                            else:
                                current_player_index = len(player_order)-1

                        #Then makes the 'current player' the next player is the play order
                        current_player = iterate_players(player_order, current_player, current_player_index)
                        while current_player in eliminated:
                            current_player = iterate_players(player_order, current_player, current_player_index)
                        
                        
                        #Notifies all clients of whos turn it is
                        for player in players:
                            player[3].send(tiles.MessagePlayerTurn(current_player).pack())
                        print("it is now player ", current_player, "'s turn")






##  After a 10 second timer, the game will start
def timer():
    sleep_duration = 10
    while sleep_duration > 0:
        print(f"you have {sleep_duration} seconds left")
        sleep(1)
        sleep_duration -= 1
    print("timer completed")
    game_loop()  #kicks everything off


# create a TCP/IP socket
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# listen on all network interfaces
server_address = ('', 30020)
sock.bind(server_address)

print('listening on {}'.format(sock.getsockname()))

sock.listen(5)

while True:
    # handle each new connection independently
    connection, client_address = sock.accept()
    print('received connection from {}'.format(client_address))
    clients_connected += 1
    client_handler(connection, client_address)

    if maximum_players == None:
        if clients_connected == 2:
            
            timer_thread = Thread(target=timer)

            timer_thread.start()

            for i in range(0, 15):
                # check the timer
                if not timer_thread.is_alive():
                    # timer is complete
                    #game loop starts
                    break

    elif clients_connected == maximum_players:
        game_loop()
                