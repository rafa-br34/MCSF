import asyncio
import json
import sys

from Modules import Protocol


async def main(host, port):
	print(json.dumps(await Protocol.async_server_status(host, int(port)), indent=3))

if __name__ == "__main__":
	asyncio.run(main(*sys.argv[1].split(':')))
