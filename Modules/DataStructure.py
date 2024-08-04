import aiohttp.client_exceptions
import requests
import aiohttp
import asyncio
import pickle
import zlib
import time

from datauri import DataURI


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

	def serialize(self):
		return {
			"hosts": [host.serialize() for host in self.hosts]
		}

	def deserialize(self, obj):
		self.hosts = [Host().deserialize(host) for host in obj["hosts"]]
		return self
	
	def serialize_file(self, filename):
		with open(filename, "wb") as file:
			pickle.dump(self.serialize(), file)
	
	def deserialize_file(self, filename):
		with open(filename, "rb") as file:
			self.deserialize(pickle.load(file))

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

	def serialize(self):
		return {
			"address": self.address,
			"servers": [server.serialize() for server in self.servers]
		}
	
	def deserialize(self, obj):
		self.address = obj["address"]
		self.servers = [Server(self).deserialize(server) for server in obj["servers"]]
		return self


class Server:
	def __init__(self, host, port=None):
		self.favicon_crc32 = 0
		self.favicon_size = 0
		self.favicon_type = None
		self.favicon_data = None
		self.favicon = None
		
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

	def update_favicon(self):
		if self.favicon:
			uri = DataURI(self.favicon)
			self.favicon_type = uri.mimetype
			self.favicon_data = uri.data
			self.favicon_size = len(uri.data)
			self.favicon_crc32 = zlib.crc32(uri.data)
	
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
			self.favicon = obj["favicon"]
			self.update_favicon()
		
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
		self.protocol_version = obj["protocol"]
	
	def parse_players(self, obj):
		self.active_players = obj["online"]
		self.max_players = obj["max"]

		# "sample" is only returned when there are active players it seems?
		for player in self.players:
			player.active = False

		if "sample" in obj:
			for player_sample in obj["sample"]:
				player = self.get_or_add_player(player_sample["name"], player_sample["id"])
				player.parse_player(player_sample)
				player.update_last_seen()
				player.active = True

	def serialize(self):
		return {
			"favicon": self.favicon,
			
			"protocol_version": self.protocol_version,
			"server_version": self.server_version,
			"secure_chat": self.secure_chat,
			"mods": [mod.serialize() for mod in self.mods],
			"port": self.port,
			"tags": list(self.tags),
			
			"active_players": self.active_players,
			"max_players": self.max_players,
			"players": [player.serialize() for player in self.players],
			
			"active": self.active
		}
	
	def deserialize(self, obj):
		self.favicon = obj["favicon"]
		self.update_favicon()

		self.protocol_version = obj["protocol_version"]
		self.server_version = obj["server_version"]
		self.secure_chat = obj["secure_chat"]
		self.mods = [Mod().deserialize(mod) for mod in obj["mods"]]
		self.port = obj["port"]
		self.tags = obj["tags"]

		self.active_players = obj["active_players"]
		self.max_players = obj["max_players"]
		self.players = [Player(self).deserialize(player) for player in obj["players"]]

		self.active = obj["active"]

		return self


class Player:
	def __init__(self, server, name=None, uuid=None):
		self.server = server
		self.name = name
		self.uuid = uuid
		self.active = False
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
		self.last_seen = time.time()

	def parse_player(self, obj):
		self.name = obj["name"]
		self.uuid = obj["id"]
		return self
	
	def serialize(self):
		return {
			"name": self.name,
			"uuid": self.uuid,
			"active": self.active,
			"premium_uuid": self.premium_uuid,
			"premium_name": self.premium_name,
			"last_seen": self.last_seen,
			"last_verified": self.last_verified
		}
	
	def deserialize(self, obj):
		self.last_verified = obj["last_verified"]
		self.last_seen = obj["last_seen"]
		self.premium_name = obj["premium_uuid"]
		self.premium_uuid = obj["premium_uuid"]
		self.active = obj["active"]
		self.uuid = obj["uuid"]
		self.name = obj["name"]
		return self

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

	def serialize(self):
		return {
			"id": self.id,
			"version": self.version
		}
	
	def deserialize(self, obj):
		self.version = obj["version"]
		self.id = obj["id"]
		return self