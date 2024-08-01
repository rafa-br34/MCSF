import subprocess
import ipaddress
import argparse
import untangle
import asyncio
import icmplib
import random
import socket
import re

from tqdm import tqdm

from Modules import DataStructure
from Modules import Protocol

c_randomize_ports = False
c_randomize_hosts = False
c_ping_scan_runners = 16
c_ping_scan = False
c_nmap_path = "nmap"
c_use_nmap = False
c_runners = 32
c_timeout = 5
c_output = "scan_results.pickle"
c_port = 25565


class _State:
	task_queue = asyncio.Queue(4096)
	host_list = DataStructure.HostList()
	running = True

g_state = _State()


def parse_arguments():
	parser = argparse.ArgumentParser(description="A simple CLI tool to scan for Minecraft servers in a specific IP range")

	parser.add_argument(
		"--target", "-t", help="The target IP address to scan.", required=True, type=str
	)

	# Optional Arguments
	parser.add_argument(
		"--ports", "-p", help=f"The range of ports to try (\"-p 10000-20000\", \"-p 25565\", \"-p 15-25 30-40 80 8080\") (default {c_port}).", nargs='+', required=False, type=str,
		default=c_port
	)

	parser.add_argument(
		"--runners", "-r", help=f"Task count (defaults to {c_runners}).", required=False, type=int,
		default=c_runners
	)

	parser.add_argument(
		"--timeout", "-T", help=f"Time to wait for a connection before giving up (defaults to {c_timeout}).", required=False, type=int,
		default=c_timeout
	)

	parser.add_argument(
		"--output", "-o", help=f"Where the results should be stored (defaults to \"{c_output}\").", required=False, type=str,
		default=c_output
	)

	parser.add_argument(
		"--randomize-ports", help=f"Randomize ports (defaults to {c_randomize_ports}).", required=False, action="store_true",
		default=c_randomize_ports
	)

	parser.add_argument(
		"--randomize-hosts", help=f"Randomize hosts (defaults to {c_randomize_hosts}).", required=False, action="store_true",
		default=c_randomize_hosts
	)

	parser.add_argument(
		"--ping-scan", help=f"Ping hosts before scanning (defaults to {c_ping_scan}).", required=False, action="store_true",
		default=c_ping_scan
	)

	parser.add_argument(
		"--ping-scan-runners", help=f"Ping scan runners (defaults to {c_ping_scan_runners}).", required=False, type=int,
		default=c_ping_scan_runners
	)

	parser.add_argument(
		"--nmap", help=f"Use Nmap for scanning (defaults to {c_use_nmap}).", required=False, action="store_true",
		default=c_use_nmap
	)

	parser.add_argument(
		"--nmap-path", help=f"Set the Nmap path (defaults to {c_nmap_path}).", required=False, type=str,
		default=c_nmap_path
	)

	return parser.parse_args()


def unpack_ranges(ranges):
	ports = set()
	for expression in ranges:
		if re.fullmatch(r"\d+-\d+", expression):
			[lower, upper] = expression.split('-')
			ports.update(range(int(lower), int(upper) + 1))
		elif re.fullmatch(r"\d+", expression):
			ports.add(int(expression))
		else:
			raise AssertionError(f"'{expression}' is a invalid range expression")
	
	assert 0 not in ports, "Port 0 was specified even thought it isn't allowed"
	assert max(ports) <= 0xFFFF, "A port greater than 0xFFFF cannot exist"
	return ports


def resolve_address(address):
	try:
		return ipaddress.ip_network(address, strict=False)
	except ValueError:
		pass

	try:
		return resolve_address(socket.gethostbyname(address))
	except OSError:
		pass

	return False


def randomize_iterable(iterable, randomize):
	return randomize and sorted(iterable, key=lambda _: random.random()) or list(iterable)


async def scanner_task(protocol, timeout):
	global g_state

	while g_state.running:
		await asyncio.sleep(random.random() * 0.125)
		[host, port] = await g_state.task_queue.get()

		result = await Protocol.async_server_status(host, port, protocol, timeout)
		if result:
			server = g_state.host_list.get_or_add_server(host, port)
			server.parse_status(result)


async def ping_hosts(hosts, runners, timeout=10):
	try:
		return await icmplib.async_multiping(hosts, 1, 0, timeout, runners)
	except (OSError, icmplib.ICMPLibError):
		return False


async def parse_hosts(arguments):
	target = resolve_address(arguments.target)

	assert target, f"Couldn't parse {arguments.target}"
	
	hosts = map(lambda host: host.compressed, target.hosts())

	if arguments.ping_scan:
		hosts = map(lambda v: v.address, filter(lambda v: v.is_alive, await ping_hosts(hosts, arguments.ping_scan_runners, arguments.timeout)))
	
	return randomize_iterable(hosts, arguments.randomize_hosts)


async def parse_ports(arguments):
	return randomize_iterable(unpack_ranges(arguments.ports), arguments.randomize_ports)


async def manual_scan(arguments):
	global g_state

	host_list = await parse_hosts(arguments)
	port_list = await parse_ports(arguments)
	task_size = len(host_list) * len(port_list)

	bar = tqdm(bar_format="{desc} Progress: {percentage:0.2f}% |{bar}{r_bar}", total=0)
	bar.total = task_size
	
	task_queue = g_state.task_queue
	for host_idx, host in enumerate(host_list):
		for port_idx, port in enumerate(port_list):
			await task_queue.put((host, port))
			
			while task_queue.full():
				await asyncio.sleep(0.05)
			
			bar.desc = f"{host}:{port} Found {g_state.host_list.server_count()} servers on {len(g_state.host_list)}"
			bar.n = host_idx * len(port_list) + port_idx + 1
			bar.refresh()

	bar.close()

	while not task_queue.empty():
		await asyncio.sleep(0.05)


async def nmap_scan(arguments):
	global g_state
	
	print("Running Nmap, this might take a long time...")
	process = subprocess.Popen(
		[
			arguments.nmap_path,
			"-sS",
			"-oX", "-",
			f"-p {','.join(arguments.ports)}", arguments.target,
			not arguments.ping_scan and "-Pn" or ""
		],
		stdout=subprocess.PIPE
	)
	result = bytes()

	while process.poll() == None:
		result += process.stdout.read()
	
	assert process.returncode == 0, "Nmap didn't return 0, did something go wrong?"

	task_queue = g_state.task_queue
	parsed = untangle.parse(result.decode())

	print("Fetching server info...")
	for host in parsed.nmaprun.host:
		address = host.address.get_attribute("addr")

		if "port" not in host.ports:
			continue

		for port_element in host.ports.port:
			await task_queue.put((address, int(port_element.get_attribute("portid"))))

	while not task_queue.empty():
		await asyncio.sleep(0.05)


async def main():
	arguments = parse_arguments()

	for _ in range(arguments.runners):
		asyncio.create_task(scanner_task(47, arguments.timeout))
	
	if arguments.nmap:
		await nmap_scan(arguments)
	else:
		await manual_scan(arguments)
	
	g_state.running = False

	print("Done, writing to file...")
	g_state.host_list.serialize_file(arguments.output)


if __name__ == "__main__":
	asyncio.run(main())