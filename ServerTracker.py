import pyperclip
import argparse
import asyncio
import pathlib
import atexit
import curses
import arrow
import json
import time

from Modules import DataStructure
from Modules import Protocol
from Modules import Widgets


c_state_file = "save_state.pickle"
c_runners = 16

class _State:
	host_list = DataStructure.HostList()
	arguments = None
	running = True
	queue = asyncio.Queue()

g_state = _State()

def load_state():
	global g_state
	g_state.host_list.deserialize_file(g_state.arguments.state_file)

def save_state():
	global g_state
	g_state.host_list.serialize_file(g_state.arguments.state_file)


async def scheduler():
	global g_state
	
	host_list = g_state.host_list
	queue = g_state.queue

	while g_state.running:
		if queue.empty():
			save_state()
			await asyncio.sleep(2.5)
			for server in host_list.server_iterator():
				await queue.put(server)

		await asyncio.sleep(0.5)

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
			server.active_players = 0
		
		for player in server.players:
			if time.time() - player.last_verified > 216000 * 12:
				await player.verify_premium_async()


def spin_text(string, size, rotation, spacing=4):
	strlen = len(string)
	
	if strlen <= size:
		return string

	rotation = rotation % (strlen + spacing)
	remainder = rotation + size - strlen
	if remainder > spacing:
		return string[rotation:rotation + size] + ' ' * (spacing + min(0, size - remainder)) + string[0:remainder - spacing]
	else:
		return string[rotation:rotation + size]

def spin_textr(string, size, rotation, spacing=4):
	return spin_text(string, size, rotation, spacing).rjust(size)

def spin_textl(string, size, rotation, spacing=4):
	return spin_text(string, size, rotation, spacing).ljust(size)


class Property:
	def __init__(self, item_type, item):
		self.item_type = item_type
		self.item = item

	def draw(self, line, tick, screen, palette):
		item = self.item

		match self.item_type:
			case "TEXT":
				screen.addstr(line, 0, item)
			
			case "SERVER":
				address = item.host.address
				port = item.port

				version = spin_textl(item.server_version or '?', 20, tick)
				host    = spin_textl(address + ':' + str(port),  26, tick) # IPv4 len: 21
				mods    = spin_textl(f"{len(item.mods)} Mods",   9,  tick)

				players = f"{item.active_players}/{item.max_players}({len(item.players)})"
				
				screen.addstr(
					line, 0,
					item.active and "[ACTIVE]" or "[INACTIVE]",
					item.active and palette.get("ONL") or palette.get("OFF")
				)
				screen.addstr(
					line, 11,
					f"{host} {version} {mods} {players}"
				)
			
			case "PLAYER":
				screen.addstr(
					line, 0,
					item.active and "[ONLINE]" or "[OFFLINE]",
					item.active and palette.get("ONL") or palette.get("OFF")
				)
				screen.addstr(
					line, 11,
					f"{item.name} ({item.uuid}) Premium name/uuid: {item.premium_name}/{item.premium_uuid} Last seen {arrow.get(item.last_seen).humanize()}"
				)
			
			case "MOD":
				screen.addstr(
					line, 3,
					f"{item.id} ({item.version})"
				)
	
	def copy(self):
		item_type = self.item_type
		source = self.item

		match item_type:
			case "TEXT":
				return source

			case _ if item_type in ["SERVER", "PLAYER", "MOD"]:
				return json.dumps(source.serialize(), indent=3)

def build_server_info(server):
	player_list = []
	mod_list = []

	for player in server.players:
		player_list.append(Property("PLAYER", player))

	for mod in server.mods:
		mod_list.append(Property("MOD", mod))

	return [
		Property("TEXT", f"Version: {server.server_version or '?'}"),
		Property("TEXT", f"Enforces secure chat: {server.secure_chat and 'Yes' or 'No'}"),
		Property("TEXT", f"Active players {server.active_players}/{server.max_players} ({len(server.players)} players seen):"),
		*player_list,
		Property("TEXT", f"Mods {len(server.mods)}:"),
		*mod_list
	]

def parse_arguments():
	parser = argparse.ArgumentParser(description="A simple text-based user interface tool to track specific Minecraft servers")

	parser.add_argument(
		"--state-file", "-s", help=f"The path in which the state file should be stored (defaults to \"{c_state_file}\").", required=False, type=str,
		default=c_state_file
	)

	parser.add_argument(
		"--runners", "-r", help=f"Task count (defaults to {c_runners}).", required=False, type=int,
		default=c_runners
	)

	return parser.parse_args()

def prepare_state():
	global g_state
	g_state.arguments = parse_arguments()

	if pathlib.Path(g_state.arguments.state_file).exists():
		load_state()
	
	atexit.register(save_state)

	asyncio.create_task(scheduler())
	for _ in range(g_state.arguments.runners):
		asyncio.create_task(ping_worker())
	

def prepare_screen(screen):
	curses.mousemask(curses.ALL_MOUSE_EVENTS)
	curses.curs_set(0)
	screen.clear()
	screen.nodelay(True)
	screen.keypad(True)
	screen.idcok(False)
	screen.idlok(False)

	if curses.can_change_color():
		curses.init_color(curses.COLOR_WHITE, 800, 800, 800)


async def main(screen: curses.window):
	global g_state

	prepare_state()
	prepare_screen(screen)

	palette = Widgets.Palette()

	palette.set("CMD", curses.COLOR_WHITE, curses.COLOR_CYAN) # Bottom bar
	palette.set("HOV", None, None, curses.A_BOLD) # Item hovered

	palette.set("ONL", curses.COLOR_WHITE, curses.COLOR_GREEN) # Online
	palette.set("OFF", curses.COLOR_WHITE, curses.COLOR_RED) # Offline
	
	scrolling_frame_states = []
	scrolling_frame = Widgets.ScrollingFrame(screen.subwin(curses.LINES - 1, curses.COLS - 1, 0, 0))
	server_view = None
	start = time.time()
	tick = 0

	def set_status(string):
		screen.addstr(curses.LINES - 1, 0, string)
		screen.chgat(curses.LINES - 1, 0, -1, palette.get("CMD"))

	while g_state.running:
		key = screen.getch()

		if 0 > key:
			await asyncio.sleep(0.05)
		
		delta = (time.time() - start) - 0.20
		if delta > 0:
			tick += 1
			start = time.time() - delta

		selection = scrolling_frame.current_item()
		match key:
			case curses.KEY_UP:
				scrolling_frame.cursor -= 1

			case curses.KEY_DOWN:
				scrolling_frame.cursor += 1
			
			case curses.KEY_PPAGE:
				scrolling_frame.cursor -= scrolling_frame.size_y - 1
			
			case curses.KEY_NPAGE:
				scrolling_frame.cursor += scrolling_frame.size_y - 1
			
			case _ if key == ord('V') or key == ord('v'):
				if server_view:
					scrolling_frame.set_state(scrolling_frame_states.pop())
					server_view = None
				elif selection:
					scrolling_frame_states.append(scrolling_frame.get_state())
					scrolling_frame.set_position(0, 0)
					server_view = selection.item
			
			case _ if key == ord('C') or key == ord('c'):
				if selection != None:
					pyperclip.copy(selection.copy())
			
			case _ if key == ord('Q') or key == ord('q'):
				g_state.running = False

		# Draw start
		screen.erase()
		if server_view:
			scrolling_frame.items = build_server_info(server_view)
		else:
			servers = list(g_state.host_list.server_iterator())
			servers.sort(key = lambda server: server.active and len(server.players), reverse=True)

			scrolling_frame.items = list(map(lambda srv: Property("SERVER", srv), servers))

		scrolling_frame.update()
		for _idx, rel, item in scrolling_frame.iterate():
			item.draw(rel, tick, screen, palette)

			if rel == scrolling_frame.cursor:
				screen.chgat(rel, 0, -1, palette.get("HOV"))

		set_status("↑/↓ & PAGE-UP/PAGE-DOWN: Move up/down, C: Copy field, V: Toggle server info view, Q: Quit")
		screen.refresh()


if __name__ == "__main__":
	def passthrough(screen):
		asyncio.run(main(screen))

	curses.wrapper(passthrough)