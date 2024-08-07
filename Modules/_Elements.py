# WIP
import curses

from collections.abc import Iterable
from abc import abstractmethod


class Color:
	def __init__(self, pair_key, foreground, background, modifiers=None):
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
		return (self.pair and curses.color_pair(self.pair_key) or 0) | (self.modifiers or 0)
	
	def set(self, foreground=None, background=None, modifiers=None):
		new_foreground = foreground if foreground != None else self.foreground
		new_background = background if background != None else self.background

		if new_background or new_foreground:
			self.background = new_background
			self.foreground = new_foreground
			curses.init_pair(self.pair_key, new_foreground, new_background)

		if modifiers != None:
			self.modifiers = modifiers
	
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
		return self.colors[key]

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

class BaseInstance:
	def __init__(self):
		self.children = []
		self._parent = None

	@property
	def parent(self):
		return self._parent

	@parent.setter
	def parent(self, value):
		if self._parent != value:
			self._parent.children.remove(self)

		if value and self not in value.children:
			value.children.append(self)

class BasePosition:
	def __init__(self):
		self.position = Vector2(0, 0)
	
	def move(self, x=None, y=None):
		position = self.position
		x = x if x != None else position.x
		y = y if y != None else position.y

		position.xy = (x, y)

class BaseSize:
	def __init__(self):
		self.size = Vector2(0, 0)

	def resize(self, x=None, y=None):
		size = self.size
		x = x if x != None else size.x
		y = y if y != None else size.y

		size.xy = (x, y)


class BaseElement(BaseInstance, BasePosition, BaseSize):
	def __init__(self, parent_screen):
		BaseInstance.__init__(self)
		BasePosition.__init__(self)
		BaseSize.__init__(self)

		self.screen: curses.window = parent_screen.subwin(0, 0)

	@abstractmethod
	def _draw_start(self):
		screen = self.screen
		screen.resize(*self.size.yx)
		screen.mvwin(*self.position.yx)
	
	@abstractmethod
	def _draw_children(self):
		for child in self.children:
			child.draw()

	@abstractmethod
	def draw(self):
		raise NotImplementedError("BaseElement::draw")


class Frame(BaseElement):
	def __init__(self, parent_screen, position=None, size=None, color=None, border=False):
		super().__init__(parent_screen)

		self.position = position if position != None else Vector2(0, 0)
		self.size = size if size != None else Vector2(0, 0)
		
		self.border = border
		self.color = color

	@abstractmethod
	def _draw_frame(self):
		screen = self.screen
		color = self.color
		if color:
			screen.bkgd(' ', color.get())
		
		if isinstance(self.border, Iterable):
			screen.border(*list(self.border))
		elif self.border:
			screen.box()

	@abstractmethod
	def draw(self):
		self._draw_start()
		self._draw_frame()
		self._draw_children()


class ScrollingFrame(Frame):
	def __init__(self, parent_screen: curses.window):
		super().__init__(parent_screen)
		self.cursor = 0
		self.scroll = 0
	
	def update(self):
		cursor = self.cursor
		scroll = self.scroll

		sy = self.size.y

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

	def iterate(self):
		scroll = self.scroll
		sy = self.size.y

		for idx, item in enumerate(self.children):
			if idx < scroll:
				continue
			if idx - scroll >= sy:
				break
			
			yield idx, idx - scroll, item

	def current_item(self):
		idx = self.scroll + self.cursor
		if idx < len(self.children):
			return self.children[idx]
	
	def set_scroll(self, cursor, scroll):
		self.cursor = cursor
		self.scroll = scroll

	def get_state(self):
		return (self.cursor, self.scroll)
	
	def set_state(self, state):
		self.set_scroll(*state)

	def _draw_children(self):
		scroll = self.scroll
		sy = self.size.y

		for idx, item in enumerate(self.children):
			
			idx = idx + item.size.y
			if idx < scroll:
				continue
			if idx - scroll >= sy:
				break
			
			item.position.y = idx
			item.draw()
			

	def draw(self):
		self._draw_start()
		self._draw_frame()
		self._draw_children()