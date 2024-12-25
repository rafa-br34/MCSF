import argparse
import json

from Modules import DataStructure

c_state_file = "save_state.pickle"
c_json_file = "save_state.json"

def parse_arguments():
	parser = argparse.ArgumentParser(description="A simple text-based user interface tool to track specific Minecraft servers")

	parser.add_argument(
		"--state-file", "-s", help=f"The state file to use (defaults to \"{c_state_file}\").", required=False, type=str,
		default=c_state_file
	)

	parser.add_argument(
		"--json-file", "-j", help=f"The json file to use (defaults to \"{c_json_file}\").", required=False, type=str,
		default=c_json_file
	)

	return parser.parse_args()

def main():
	arguments = parse_arguments()

	host_list = DataStructure.HostList()
	host_list.deserialize_file(arguments.state_file)

	with open(arguments.json_file, "w") as file:
		json.dump(DataStructure.get_dict(host_list), file, indent=4)

if __name__ == "__main__":
	main()