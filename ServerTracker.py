import pyperclip
import asyncio
import pathlib
import atexit
import curses
import time

from Modules import DataStructure
from Modules import Protocol
from Modules import Widgets


c_save_file = "save_state.pickle"
c_ping_workers = 12

class _State:
	host_list = DataStructure.HostList()
	running = True
	queue = asyncio.Queue()

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
				await player.verify_premium_async()


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


async def main(screen: curses.window):
	global g_state


	if pathlib.Path(c_save_file).exists():
		load_state()
	
	atexit.register(save_state)

	asyncio.create_task(scheduler())
	for _ in range(c_ping_workers):
		asyncio.create_task(ping_worker())


	curses.mousemask(curses.ALL_MOUSE_EVENTS)
	curses.curs_set(0)
	screen.clear()
	screen.nodelay(True)
	screen.keypad(True)

	palette = Widgets.Palette()

	if curses.can_change_color():
		curses.init_color(curses.COLOR_WHITE, 800, 800, 800)

	palette.set("CMD", curses.COLOR_WHITE, curses.COLOR_CYAN)
	palette.set("SEL", curses.COLOR_WHITE, curses.COLOR_GREEN)
	palette.set("HOV", curses.COLOR_WHITE, curses.COLOR_BLACK, curses.A_BLINK)
	
	scrolling_frame_states = []
	scrolling_frame = Widgets.ScrollingFrame(screen.subwin(curses.LINES - 1, -1, 0, 0))
	server_view = None
	start = time.time()
	tick = 0

	def set_status(string):
		screen.addstr(curses.LINES - 1, 0, string)
		screen.chgat(curses.LINES - 1, 0, -1, palette.get("CMD"))

	def draw_server(line, server, tick, hover):
		address = server.host.address
		port = server.port

		players = f"{server.active_players}/{server.max_players}({len(server.players)})"
		version = f"{spin_string(server.server_version or '?', 12, tick):<12}"
		active = server.active and ' ' or '▼'
		host = f"{spin_string(address + ':' + str(port), 21, tick):<21}"

		screen.addstr(line, 0, f"{host} {version} {active} {players}")
		if hover:
			screen.chgat(line, 0, -1, palette.get("HOV"))
	
	def server_info(server):
		player_list = []
		for player in server.players:
			player_list.append(f"\t{player.name} ({player.uuid}) Premium name/uuid: {player.premium_name}/{player.premium_uuid}")

		return [
			f"Version: {server.server_version or '?'}",
			f"Active players {server.active_players}/{server.max_players}",
			*player_list,
		]

	while g_state.running:
		key = screen.getch()

		if 0 > key:
			await asyncio.sleep(0.05)
		
		delta = (time.time() - start) - 0.25
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
				else:
					scrolling_frame_states.append(scrolling_frame.get_state())
					scrolling_frame.set_position(0, 0)
					server_view = selection
					
			
			case _ if key == ord('C') or key == ord('c'):
				if server_view and selection != None:
					pyperclip.copy(str(selection))

		# Draw start
		screen.clear()
		if server_view:
			scrolling_frame.items = server_info(server_view)
			scrolling_frame.update()

			for _idx, rel, item in scrolling_frame.iterate():
				screen.addstr(rel, 0, item)
				if rel == scrolling_frame.cursor:
					screen.chgat(rel, 0, -1, palette.get("HOV"))
			
			set_status("↑/↓ & PAGE-UP/PAGE-DOWN: Move up/down, C: Copy field, V: Exit server info")
		else:
			servers = list(g_state.host_list.server_iterator())
			servers.sort(key = lambda server: server.active and len(server.players), reverse=True)

			scrolling_frame.items = servers
			scrolling_frame.update()

			for _idx, rel, server in scrolling_frame.iterate():
				draw_server(rel, server, tick, rel == scrolling_frame.cursor)
			
			set_status("ESC: Options, ↑/↓ & PAGE-UP/PAGE-DOWN: Move up/down, V: View server info")
		
		screen.refresh()


if __name__ == "__main__":
	def passthrough(screen):
		asyncio.run(main(screen))

	curses.wrapper(passthrough)