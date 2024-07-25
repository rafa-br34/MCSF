import asyncio
import pathlib
import pickle
import time

from mcproto.packets.handshaking.handshake import Handshake, NextState
from mcproto.packets.status.status import StatusRequest
from mcproto.packets.packet import PacketDirection, GameState
from mcproto.connection import TCPAsyncConnection
from mcproto.packets import async_write_packet, async_read_packet, generate_packet_map
from tqdm import tqdm

STATUS_CLIENTBOUND_MAP = generate_packet_map(PacketDirection.CLIENTBOUND, GameState.STATUS)

import DataStructure

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
	with open(c_save_file, "rb") as file:
		g_state.host_list.deserialize(pickle.load(file))

def save_state():
	global g_state
	with open(c_save_file, "wb") as file:
		pickle.dump(g_state.host_list.serialize(), file)

async def server_status(address, port, protocol=47, timeout=5):
	try:
		async with await TCPAsyncConnection.make_client((address, port), timeout) as client:
			await async_write_packet(client, Handshake(
				protocol_version=protocol,
				server_address=address,
				server_port=port,
				next_state=NextState.STATUS
			))
			await async_write_packet(client, StatusRequest())

			return (await async_read_packet(client, STATUS_CLIENTBOUND_MAP)).data
	except OSError:
		return False

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
		result = await server_status(server.host.address, server.port)

		if result:
			server.active = True
			server.parse_version(result["version"])
			server.parse_players(result["players"])
		else:
			server.active = False
		
		for player in server.players:
			if time.time() - player.last_verified > 216000 * 12:
				player.verify_premium()


async def main():
	global g_state
	
	if pathlib.Path(c_save_file).exists():
		load_state()

	asyncio.create_task(scheduler())
	for _ in range(c_ping_workers):
		asyncio.create_task(ping_worker())

	while g_state.running:
		await asyncio.sleep(0.05)

		servers = list(g_state.host_list.server_iterator())
		servers.sort(key = lambda server: f"{server.host.address}:{server.port}")
		
		for idx, server in enumerate(servers):
			address = server.host.address
			port = server.port
			bar = None
			if idx in g_state.bars:
				bar = g_state.bars[idx]
			else:
				bar = tqdm(bar_format="{desc}", total=0, position=len(g_state.bars))
				g_state.bars[idx] = bar

			bar.desc = f"{address + ':' + str(port):<21} {server.server_version or '?':<12} {server.active and ' ' or '▼'} {server.active_players}/{server.max_players}({len(server.players)})"
			bar.refresh()
		

if __name__ == "__main__":
	asyncio.run(main())