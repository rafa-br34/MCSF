import asyncio
import pathlib
import atexit
import time

from tqdm import tqdm

from Modules import DataStructure
from Modules import Protocol

c_save_file = "save_state.pickle"
c_ping_workers = 8

class _State:
	host_list = DataStructure.HostList()
	running = True
	queue = asyncio.Queue()
	bars = {}

g_state = _State()

def load_state():
	global g_state
	g_state.host_list.deserialize_file(c_save_file)

def save_state():
	global g_state
	g_state.host_list.serialize_file(c_save_file)


async def scheduler():
	global g_state
	
	host_list = g_state.host_list
	queue = g_state.queue

	while g_state.running:
		if queue.empty():
			save_state()
			for server in host_list.server_iterator():
				await queue.put(server)

		await asyncio.sleep(2.5)

async def ping_worker():
	global g_state

	while g_state.running:
		server = await g_state.queue.get()
		result = await Protocol.async_server_status(server.host.address, server.port)

		if result:
			server.active = True
			server.parse_status(result)
		else:
			server.active = False
		
		for player in server.players:
			if time.time() - player.last_verified > 216000 * 12:
				player.verify_premium()

def spin_string(string, size, rotation, spacing=4):
	strlen = len(string)
	
	if strlen <= size:
		return string

	rotation = rotation % (strlen + spacing)
	remainder = rotation + size - strlen
	if remainder > spacing:
		return string[rotation:rotation + size] + ' ' * (spacing + min(0, size - remainder)) + string[0:remainder - spacing]
	else:
		return string[rotation:rotation + size]

async def main():
	global g_state
	
	if pathlib.Path(c_save_file).exists():
		load_state()
	
	atexit.register(save_state)

	asyncio.create_task(scheduler())
	for _ in range(c_ping_workers):
		asyncio.create_task(ping_worker())

	start = time.time()
	tick = 0

	while g_state.running:
		await asyncio.sleep(0.05)

		delta = (time.time() - start) - 0.25
		if delta > 0:
			tick += 1
			start = time.time() - delta

		servers = list(g_state.host_list.server_iterator())
		servers.sort(key = lambda server: server.active and len(server.players), reverse=True)
		
		for idx, server in enumerate(servers):
			address = server.host.address
			port = server.port
			bar = None
			if idx in g_state.bars:
				bar = g_state.bars[idx]
			else:
				bar = tqdm(bar_format="{desc}", total=0, position=len(g_state.bars))
				g_state.bars[idx] = bar
			
			bar.desc = f"{spin_string(address + ':' + str(port), 21, tick):<21} {spin_string(server.server_version or '?', 12, tick):<12} {server.active and ' ' or '▼'} {server.active_players}/{server.max_players}({len(server.players)})"
			bar.refresh()

if __name__ == "__main__":
	asyncio.run(main())