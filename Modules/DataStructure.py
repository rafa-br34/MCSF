import requests
import aiohttp.client_exceptions
import aiohttp
import asyncio
import base64
import pickle
import zlib
import time

from datauri import DataURI


def get_dict(item):
	if hasattr(item, "get_dict"):
		return {name: get_dict(value) for name, value in item.get_dict().items()}
	elif hasattr(item, "__dict__"):
		return {name: get_dict(value) for name, value in item.__dict__.items()}
	elif isinstance(item, (list, tuple, set)):
		return [get_dict(value) for value in item]
	elif isinstance(item, bytes):
		return base64.b64encode(item).decode()
	else:
		return item


class HostList:
	def __init__(self):
		self.hosts = []

	def get_or_add_host(self, address):
		host = next((host for host in self.hosts if host.address == address), None)

		if not host:
			host = Host(address)
			self.hosts.append(host)
		
		return host
	
	def get_or_add_server(self, address, port):
		return self.get_or_add_host(address).get_or_add_server(port)
	
	def server_iterator(self):
		for host in self.hosts:
			for server in host.servers:
				yield server

	def server_count(self):
		server_count = 0

		for host in self.hosts:
			server_count += len(host.servers)

		return server_count
	
	def serialize_file(self, filename):
		with open(filename, "wb") as file:
			pickle.dump(self, file)
	
	def deserialize_file(self, filename):
		with open(filename, "rb") as file:
			self.hosts = pickle.load(file).hosts

class Host:
	def __init__(self, address=None):
		self.address = address
		self.servers = []

	def get_server(self, port):
		return next((server for server in self.servers if server.port == port), None)

	def get_or_add_server(self, port):
		server = self.get_server(port)
		
		if not server:
			server = Server(self, port)
			self.servers.append(server)
		
		return server
	
	def remove_server(self, port):
		self.servers.remove(self.get_server(port))

class Favicon:
	def __init__(self):
		self.crc32 = 0
		self.size = 0
		self.type = None
		self.data = None

	def load_multipart(self, multipart):
		uri = DataURI(multipart)
		self.crc32 = zlib.crc32(uri.data)
		self.size = len(uri.data)
		self.type = uri.mimetype
		self.data = uri.data

class Server:
	def __init__(self, host, port=None):
		self.favicon = Favicon()
		
		self.protocol_version = None
		self.server_version = None
		self.secure_chat = None
		self.mods = []
		self.host = host
		self.port = port
		self.tags = set()

		self.active_players = 0
		self.max_players = 0
		self.players = list()

		self.active = False

	def get_play_time(self):
		return sum([player.play_time for player in self.players])

	def get_player(self, name=None, uuid=None):
		return next((player for player in self.players if player.name == name or player.uuid == uuid), None)

	def get_or_add_player(self, name=None, uuid=None):
		player = self.get_player(name, uuid)

		if not player:
			player = Player(self, name, uuid)
			self.players.append(player)

		return player
	
	def remove_player(self, name=None, uuid=None):
		self.players.remove(self.get_player(name, uuid))

	def update_favicon(self, favicon):
		self.favicon.load_multipart(favicon)
	
	def parse_status(self, obj):
		if "version" in obj:
			self.parse_version(obj["version"])

		if "players" in obj:
			self.parse_players(obj["players"])
		
		if "forgeData" in obj:
			self.parse_forge_data(obj["forgeData"])
		elif "modinfo" in obj:
			self.parse_fml_data(obj["modinfo"])
		
		if "favicon" in obj:
			self.update_favicon(obj["favicon"])
		
		if "enforcesSecureChat" in obj:
			self.secure_chat = obj["enforcesSecureChat"]
	
	def parse_forge_data(self, obj):
		if "mods" in obj:
			mod_list = []
			for mod in obj["mods"]:
				mod_list.append(Mod().parse_forge(mod))

			self.mods = mod_list
	
	def parse_fml_data(self, obj):
		if "modList" in obj:
			mod_list = []
			for mod in obj["modList"]:
				mod_list.append(Mod().parse_fml(mod))

			self.mods = mod_list

	def parse_version(self, obj):
		if "name" in obj:
			self.server_version = obj["name"]
		
		if "protocol" in obj:
			self.protocol_version = obj["protocol"]
	
	def parse_players(self, obj):
		self.active_players = obj["online"]
		self.max_players = obj["max"]

		if "sample" in obj:
			for player_sample in obj["sample"]:
				player = self.get_or_add_player(player_sample["name"], player_sample["id"])
				player.parse_player(player_sample)
				player.update_last_seen()
				player.active = True
		else: # sample is only set when there are active players it seems?
			for player in self.players:
				player.active = False

	def get_dict(self):
		return {key: value for key, value in self.__dict__.items() if key != "host"}

class Player:
	def __init__(self, server, name=None, uuid=None):
		self.server = server
		self.name = name
		self.uuid = uuid
		self.active = False
		self.play_time = 0
		self.last_seen = 0
		self.last_verified = 0
		self.premium_uuid = None
		self.premium_name = None

	def verify_premium(self):
		try:
			self.premium_uuid = requests.get(f"https://sessionserver.mojang.com/session/minecraft/profile/{self.uuid}").status_code == 200
			self.premium_name = requests.get(f"https://api.mojang.com/users/profiles/minecraft/{self.name}").status_code == 200
		except OSError:
			return
		
		self.last_verified = time.time()
	
	async def verify_premium_async(self):
		exceptions = aiohttp.client_exceptions
		try:
			async with aiohttp.ClientSession() as session:
				self.premium_uuid = (await session.get(f"https://sessionserver.mojang.com/session/minecraft/profile/{self.uuid}")).status == 200
				self.premium_name = (await session.get(f"https://api.mojang.com/users/profiles/minecraft/{self.name}")).status == 200
		except (OSError, exceptions.ClientError):
			return
		
		self.last_verified = time.time()

	def update_last_seen(self):
		current_time = time.time()

		if self.active:
			self.play_time += current_time - self.last_seen
		
		self.last_seen = current_time

	def parse_player(self, obj):
		self.name = obj["name"]
		self.uuid = obj["id"]
		return self
	
	def get_dict(self):
		return {key: value for key, value in self.__dict__.items() if key != "server"}

class Mod:
	def __init__(self, mod_id=None, mod_version=None):
		self.version = mod_version
		self.id = mod_id
	
	def parse_forge(self, obj):
		self.version = obj["modmarker"]
		self.id = obj["modId"]
		return self
	
	def parse_fml(self, obj):
		self.version = obj["version"]
		self.id = obj["modid"]
		return self