# test.py
import asyncio
import json
import random
import pygame
import threading
import websockets

SERVER_IP = 'localhost'
SERVER_PORT = 8766
NICKNAME = 'CoolCat' + str(random.randint(100, 999))

class GameClient:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((800, 600))
        pygame.display.set_caption("Game Client")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 24)

        self.game_state = {
            'my_id': NICKNAME,
            'my_pos': [5, 5],
            'current_map': 'Loading Zone...',
            'other_players': {},
            'npcs': {},
            'map_dimensions': [20, 10],
            'chat_log': [],
            'last_server_update_time': 0
        }

        self.websocket = None
        self.connect_to_server()

        self.running = True
        self.input_str = ''

    def connect_to_server(self):
        threading.Thread(target=self.connect_to_server_thread).start()

    def connect_to_server_thread(self):
        asyncio.run(self.pokemmo_client_main_loop())

    async def pokemmo_client_main_loop(self):
        uri = f"ws://{SERVER_IP}:{SERVER_PORT}"
        async with websockets.connect(uri, ping_interval=20, ping_timeout=20) as websocket:
            self.websocket = websocket
            await websocket.send(json.dumps({'action':'client_hello','nickname':NICKNAME,'client_version':'0.1'}))
            async for m in websocket:
                self.handle_server_message(m)

    def handle_server_message(self, data_json):
        try:
            data = json.loads(data_json)
            message_type = data.get('type')
            if message_type == 'world_update':
                self.game_state['my_pos'] = data.get('my_pos', self.game_state['my_pos'])
                self.game_state['current_map'] = data.get('map_id', self.game_state['current_map'])
                self.game_state['map_dimensions'] = data.get('map_dimensions', self.game_state['map_dimensions'])
                new_other = {p['id']:{'pos':p['pos']} for p in data.get('other_players', [])}
                self.game_state['other_players'] = new_other
                new_npcs = {n['id']:{'pos':n['pos'],'name':n.get('name','NPC')} for n in data.get('npcs', [])}
                self.game_state['npcs'] = new_npcs
            elif message_type == 'chat_message':
                chat_line = f"[{data.get('sender','Unknown')}]: {data.get('message','')}" 
                self.game_state['chat_log'].append(chat_line)
            elif message_type == 'event_notification':
                pass
            elif message_type == 'connection_ack':
                self.game_state['my_id'] = data.get('your_id', NICKNAME)
        except:
            pass

    def run(self):
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN:
                        self.send_command()
                    elif event.key == pygame.K_BACKSPACE:
                        self.input_str = self.input_str[:-1]
                    else:
                        self.input_str += event.unicode

            keys = pygame.key.get_pressed()
            if keys[pygame.K_w]: 
                asyncio.run(self.websocket.send(json.dumps({'action':'move','direction':'up'})))
            if keys[pygame.K_a]: 
                asyncio.run(self.websocket.send(json.dumps({'action':'move','direction':'left'})))
            if keys[pygame.K_s]: 
                asyncio.run(self.websocket.send(json.dumps({'action':'move','direction':'down'})))
            if keys[pygame.K_d]: 
                asyncio.run(self.websocket.send(json.dumps({'action':'move','direction':'right'})))

            self.screen.fill((0, 0, 0))

            header = f"--- Map: {self.game_state['current_map']} | You: {self.game_state['my_id']} @ {self.game_state['my_pos']} ---"
            text = self.font.render(header, True, (255, 255, 255))
            self.screen.blit(text, (10, 10))

            grid = [['.' for _ in range(self.game_state['map_dimensions'][0])] for _ in range(self.game_state['map_dimensions'][1])]
            for npc_data in self.game_state['npcs'].values():
                x, y = npc_data.get('pos', [None, None])
                if x is not None and 0 <= x < self.game_state['map_dimensions'][0] and 0 <= y < self.game_state['map_dimensions'][1]:
                    grid[y][x] = 'N'
            for player_id, player_data in self.game_state['other_players'].items():
                x, y = player_data.get('pos', [None, None])
                if x is not None and 0 <= x < self.game_state['map_dimensions'][0] and 0 <= y < self.game_state['map_dimensions'][1]:
                    grid[y][x] = 'P'
            my_x, my_y = self.game_state['my_pos']
            if 0 <= my_x < self.game_state['map_dimensions'][0] and 0 <= my_y < self.game_state['map_dimensions'][1]:
                grid[my_y][my_x] = '@'
            for row_idx, row in enumerate(grid):
                text = self.font.render(f"{row_idx:02d} {' '.join(row)}", True, (255, 255, 255))
                self.screen.blit(text, (10, 40 + row_idx * 20))

            chat_y = 40 + len(grid) * 20 + 20
            text = self.font.render('--- Chat Log (Last 5) ---', True, (255, 255, 255))
            self.screen.blit(text, (10, chat_y))
            chat_y += 20
            for chat_entry in self.game_state['chat_log'][-5:]:
                text = self.font.render(chat_entry, True, (255, 255, 255))
                self.screen.blit(text, (10, chat_y))
                chat_y += 20

            text = self.font.render('> ' + self.input_str, True, (255, 255, 255))
            self.screen.blit(text, (10, chat_y + 20))

            pygame.display.flip()
            self.clock.tick(60)

        pygame.quit()

    def send_command(self):
        raw = self.input_str.strip()
        cmd, *rest = raw.split(' ', 1)
        payload = {}
        if cmd == 'talk': 
            payload = {'action':'chat','message':rest[0]}
        elif cmd == 'interact': 
            payload = {'action':'interact_nearby'}
        elif cmd == 'quit': 
            asyncio.run(self.websocket.send(json.dumps({'action':'client_disconnecting'})))
            self.running = False
        if payload: 
            asyncio.run(self.websocket.send(json.dumps(payload)))
        self.input_str = ''

if __name__ == '__main__':
    game_client = GameClient()
    game_client.run()
