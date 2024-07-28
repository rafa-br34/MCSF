import asyncio

from mcproto.packets.handshaking.handshake import Handshake, NextState
from mcproto.packets.status.status import StatusRequest
from mcproto.packets.packet import PacketDirection, GameState
from mcproto.connection import TCPAsyncConnection
from mcproto.packets import async_write_packet, async_read_packet, generate_packet_map

STATUS_CLIENTBOUND_MAP = generate_packet_map(PacketDirection.CLIENTBOUND, GameState.STATUS)


async def async_server_status(address, port, protocol=47, timeout=5):
	exceptions = asyncio.exceptions
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
	except (KeyError, OSError, exceptions.TimeoutError, exceptions.CancelledError):
		return False