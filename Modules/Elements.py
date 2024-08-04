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


class Vector2:
	def __init__(self, x=0, y=0):
		self.x = x
		self.y = y
	
	@property
	def xx(self):
		return (self.x, self.x)
	
	@property
	def xy(self):
		return (self.x, self.y)
	
	@xy.setter
	def xy(self, value):
		self.x = value[0]
		self.y = value[1]
	
	@property
	def yy(self):
		return (self.y, self.y)
	
	@property
	def yx(self):
		return (self.y, self.x)
	
	@yx.setter
	def yx(self, value):
		self.y = value[0]
		self.x = value[1]

	def __eq__(self, value):
		return self.x == value.x and self.y == value.y
	
	def __hash__(self):
		return hash(self.x + self.y * self.x)

class BaseElement:
	def __init__(self, parent_screen):
		self.position = Vector2(0, 0)
		self.size = Vector2(0, 0)

		self.screen: curses.window = parent_screen.subwin(0, 0)

	def resize(self, x=None, y=None):
		size = self.size
		x = x if x != None else size.x
		y = y if y != None else size.y

		size.xy = (x, y)

	def move(self, x=None, y=None):
		position = self.position
		x = x if x != None else position.x
		y = y if y != None else position.y

		position.xy = (x, y)
	
	def draw_start(self):
		screen = self.screen
		screen.resize(*self.size.yx)
		screen.mvwin(*self.position.yx)


class ScrollingFrame(BaseElement):
	def __init__(self, parent_screen: curses.window):
		super().__init__(parent_screen)
		self.cursor = 0
		self.scroll = 0
		self.items = []
	
	def update(self):
		cursor = self.cursor
		scroll = self.scroll

		item_count = len(self.items)
		sy = min(item_count, self.size.y)

		nsy = sy - 1

		if cursor < 0:
			scroll += cursor
			cursor = 0
		elif cursor > nsy:
			scroll += cursor - nsy
			cursor = nsy
		
		scroll = min(item_count - 1 - nsy, scroll)
		scroll = max(0, scroll)
		cursor = max(0, cursor)

		self.cursor = cursor
		self.scroll = scroll

	def iterate(self):
		scroll = self.scroll
		sy = self.size.y

		for idx, item in enumerate(self.items):
			if idx < scroll:
				continue
			if idx - scroll >= sy:
				break
			
			yield idx, idx - scroll, item

	def current_item(self):
		idx = self.scroll + self.cursor

		if len(self.items) > idx:
			return self.items[idx]
	
	def set_scroll(self, cursor, scroll):
		self.cursor = cursor
		self.scroll = scroll

	def get_state(self):
		return (self.cursor, self.scroll)
	
	def set_state(self, state):
		self.set_scroll(*state)