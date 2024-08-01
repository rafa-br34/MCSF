import curses

class Color:
	def __init__(self, pair_key, foreground, background, modifiers):
		self.foreground = foreground
		self.background = background
		self.modifiers = modifiers
		self.pair_key = pair_key
		
		if foreground and background:
			self.pair = True
			curses.init_pair(pair_key, foreground, background)
		else:
			self.pair = False
	
	def get(self):
		return (self.pair and curses.color_pair(self.pair_key) or 0) | self.modifiers
	
	def __hash__(self):
		return hash(hash(self.foreground) + hash(self.background) + hash(self.modifiers))


class Palette:
	def __init__(self):
		self.colors = {}

	def set(self, key, foreground, background, modifiers=0):
		if key in self.colors:
			return
		
		self.colors[key] = Color(len(self.colors) + 1, foreground, background, modifiers)
	
	def get(self, key):
		return self.colors[key].get()


class ScrollingFrame:
	def __init__(self, screen: curses.window):
		self.screen = screen
		self.cursor = 0
		self.scroll = 0
		self.size_y = 0
		self.size_x = 0
		self.items = []
	
	def update(self):
		cursor = self.cursor
		scroll = self.scroll

		[sy, sx] = self.screen.getmaxyx()

		item_count = len(self.items)
		sy = min(item_count, sy)

		nsy = sy - 1

		if cursor < 0:
			scroll += cursor
			cursor = 0
		elif cursor > nsy:
			scroll += cursor - nsy
			cursor = nsy
		
		scroll = min(item_count - 1 - nsy, scroll)
		scroll = max(0, scroll)

		self.cursor = cursor
		self.scroll = scroll
		self.size_y = sy
		self.size_x = sx

	def iterate(self):
		scroll = self.scroll
		sy = self.size_y

		for idx, item in enumerate(self.items):
			if idx < scroll:
				continue
			if idx - scroll >= sy:
				break
			
			yield idx, idx - scroll, item

	def current_item(self):
		idx = self.scroll + self.cursor
		if idx < len(self.items):
			return self.items[idx]
	
	def set_position(self, cursor, scroll):
		self.cursor = cursor
		self.scroll = scroll

	def get_state(self):
		return (self.cursor, self.scroll)
	
	def set_state(self, state):
		self.set_position(*state)