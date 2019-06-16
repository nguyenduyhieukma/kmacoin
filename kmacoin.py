#!/usr/bin/env python3
from default_node_config import DEFAULT_NODE_CONFIG
from kmacoin.globaldef.signature import generate_key, public_key_to_bytes, \
    private_key_to_bytes
from kmacoin.network.vlp import PROPAGATION_SPEED, NetworkVisualizer
from kmacoin.atnode.workers.nodelauncher import NodeLauncher
from kmacoin.atnode.workers.blockvisualizer import BlockVisualizer
from kmacoin.atnode.node import Node

from typing import List

import sys
import os
import random
import copy


class ConfigLoader(object):
    """This class loads user configuration settings."""

    # `NODES_CONFIG_FILENAME` in current folder is the file containing user
    # settings.
    NODES_CONFIG_FILENAME = "nodes_conf.py"

    # `ROOT_DIRNAME` in current folder is the parent of all nodes' auto-
    # generated data directories.
    ROOT_DIRNAME = "kmacoin_root"

    # `KEY_FILENAME` in a node's data directory is the file to store newly
    # generated private key for that node.
    KEY_FILENAME = "key"

    # The prefix before each auto-generated name
    NAME_PREFIX = "N"

    def __init__(self):
        self.node_names = set()

    def complete_config(self, conf: dict):
        """
        Complete a node's configuration by adding default options for missing
        attributes.

        Args:
            conf: a dictionary contains user settings.

        Returns:
            a dictionary with full settings.

        """

        # overwrite default settings
        result_conf = copy.deepcopy(DEFAULT_NODE_CONFIG)
        for k, v in conf.items():
            result_conf[k] = v

        # generate a unique name if not given
        if "NAME" not in result_conf:
            result_conf["NAME"] = ConfigLoader.NAME_PREFIX + str(
                len(self.node_names) + 1)

        if result_conf["NAME"] in self.node_names:
            print("Duplicate node name found!")
            sys.exit(1)

        self.node_names.add(result_conf["NAME"])

        # virtual location
        if "VIRTUAL_LOCATION" not in result_conf:
            k = PROPAGATION_SPEED
            result_conf["VIRTUAL_LOCATION"] = (k * random.random(),
                                               k * random.random())

        # data directory
        if "DATA_DIRECTORY" not in result_conf:
            result_conf["DATA_DIRECTORY"] = os.path.abspath(os.path.join(
                ConfigLoader.ROOT_DIRNAME, result_conf["NAME"]))

        os.makedirs(result_conf["DATA_DIRECTORY"], exist_ok=True)

        # node owner's account
        if "OWNER_ACCOUNT" in conf:
            result_conf["OWNER_ACCOUNT"] = conf["OWNER_ACCOUNT"]
        else:
            private_key, public_key = generate_key()
            result_conf["OWNER_ACCOUNT"] = public_key_to_bytes(
                public_key).hex()
            with open(os.path.join(result_conf["DATA_DIRECTORY"],
                                   ConfigLoader.KEY_FILENAME), "wb") as f:
                f.write(private_key_to_bytes(private_key))

        return result_conf


if __name__ == '__main__':
    # start network visualizing
    NetworkVisualizer().start()

    # import `nodes_conf`
    nodes_conf = []
    cmd = "from {} import nodes_conf".format(
        ConfigLoader.NODES_CONFIG_FILENAME.split(".")[0])
    exec(cmd)

    # launch nodes
    config_loader = ConfigLoader()
    nodes: List[Node] = []
    for node_conf in nodes_conf:
        complete_conf = config_loader.complete_config(node_conf)
        nodes.append(Node(complete_conf))
        launcher = NodeLauncher(nodes[-1])
        print("\nLaunching node: {}...".format(complete_conf["NAME"]))
        launcher.start()
        launcher.join()

    BlockVisualizer(nodes[0]).start()
