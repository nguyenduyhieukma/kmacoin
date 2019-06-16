from kmacoin.network.visualizing import visualize, Event, PROPAGATION_SPEED

from socket import socket
from threading import Thread, Lock
from multiprocessing import Queue, Process

import time
import struct
import math

from typing import Tuple, Dict, Optional, List
Location = Tuple[float, float]
Address = Tuple[str, int]


class VLPState(object):
    """
    This class represents a VLP state.

    A VLP state is in fact a list of currently in use sockets associated with
    their locations and peer-locations. Accesses to a VLP State must be
    synchronized.

    Attributes:
        vlpsockets: socket -> [location, peer-location, name]. A dictionary of
            currently in use sockets.
        vlpsockets_lock: a lock which is used to synchronize accesses to the
            VLP state

    """
    vlpsockets: Dict[socket, List]

    def __init__(self):
        self.vlpsockets = {}
        self.vlpsockets_lock = Lock()

    def add_socket(self, s: socket, loc: Location, peer_loc: Location = None,
                   name: str = None) -> bool:
        """Add a socket to this VLP state, return True if actually added."""
        with self.vlpsockets_lock:
            if s not in self.vlpsockets:
                self.vlpsockets[s] = [loc, peer_loc, name]
                return True
            else:
                return False

    def remove_socket(self, s: socket) -> bool:
        """Remove a socket from this state, return True if actually removed."""
        with self.vlpsockets_lock:
            if s in self.vlpsockets:
                del self.vlpsockets[s]
                return True
            else:
                return False

    def update_peer_location(self, s: socket, peer_loc: Location) -> None:
        """Update peer location of a socket."""
        with self.vlpsockets_lock:
            self.vlpsockets[s][1] = peer_loc


# the only VLP state of the program's current instance:
vlpstate = VLPState()

# An event queue which is used to send events to a visualizer
event_q: Optional[Queue] = None


class NetworkVisualizer(Thread):
    def run(self):
        global event_q, vlpstate

        # only one instance of network visualizer is allowed
        assert not event_q

        # synchronize to current VLP state
        with vlpstate.vlpsockets_lock:
            event_q = Queue()
            visualizer = Process(target=visualize, args=(event_q,))
            visualizer.start()
            for s, (loc, peer_loc, name) in vlpstate.vlpsockets.items():
                event_q.put((Event.CREATE_SOCKET, loc, name))
                if peer_loc:
                    event_q.put((Event.CONNECT, loc, peer_loc))

        # block current thread
        visualizer.join()

        # visualizing has stopped, remove the event queue
        event_q = None


class LazyTransmitter(Thread):
    """
    A lazy transmitter delays transmitting some data for a specific amount of
    time.

    Attributes:
        data: the data to be sent.
        s: the socket which is used to send the data.
        sleep_time: the delay time.
        prev_lt: a previous lazy transmitter, must finish its task before
            current transmitter actually transmit the data.

    """
    def __init__(self, data: bytes, s: socket, sleep_time: float,
                 prev_lt: 'LazyTransmitter'):
        super().__init__()
        self.s = s
        self.sleep_time = sleep_time
        self.data = data
        self.prev_lt = prev_lt

    def run(self):
        # sleep
        time.sleep(self.sleep_time)

        # wait for previous transmitter
        if self.prev_lt is not None:
            self.prev_lt.join()

        # send the data
        try:
            self.s.sendall(self.data)
        except OSError:
            pass  # exception on the sending thread won't be caught


class VLPSocket(object):
    """
    A wrapper of socket, implementing the VLP protocol.

    Notes: only a small interface, which consists of basic socket methods,
    is provided.

    Attributes:
        virt_loc: the virtual location.
        s: the wrapped socket.
        virt_latency: the virtual latency.
        peer_virt_loc: the virtual location of remote peer.
        latest_lt: the latest lazy transmitter ever created. This keeps the
            messages sent by the socket in order.

    """
    def __init__(self, virt_loc: Location, s: socket = None,
                 virt_latency: float = None, peer_virt_loc: Location = None,
                 name: str = ""):

        if not s:
            self.s = socket()

        # `virt_latency` and `peer_virt_loc` must be given if `s` given
        else:
            self.s = s
            assert peer_virt_loc is not None
            assert virt_latency is not None

        self.virt_loc = virt_loc
        self.virt_latency = virt_latency
        self.peer_virt_loc = peer_virt_loc
        self.name = name
        self.latest_lt = None

        # generate events if successfully add the socket to VLP state
        if vlpstate.add_socket(self.s, self.virt_loc, self.peer_virt_loc):
            if event_q:
                event_q.put((Event.CREATE_SOCKET, self.virt_loc, self.name))
                if self.peer_virt_loc:
                    event_q.put((Event.CONNECT, self.virt_loc,
                                 self.peer_virt_loc))

    def bind(self, address: Address) -> None:
        """Bind this socket to an address."""
        self.s.bind(address)

    def listen(self, backlog: int = 5) -> None:
        """Start listening for connections."""
        return self.s.listen(backlog)

    def accept(self) -> Tuple['VLPSocket', Address]:
        """Accept a connection."""
        to_client_socket, client_addr = self.s.accept()

        # exchange virtual location info
        to_client_socket.send(struct.pack("ff", *self.virt_loc))
        client_virt_loc = struct.unpack("ff", to_client_socket.recv(8))

        # get connection latency
        virt_latency = VLPSocket.get_latency(self.virt_loc, client_virt_loc)

        # wrap and return the socket
        vlps = VLPSocket(s=to_client_socket, virt_loc=self.virt_loc,
                         virt_latency=virt_latency,
                         peer_virt_loc=client_virt_loc)
        return vlps, client_addr

    def connect(self, address: Address) -> None:
        """Connect to an address."""
        self.s.connect(address)

        # exchange virtual location info
        self.s.send(struct.pack("ff", *self.virt_loc))
        server_virt_loc = struct.unpack("ff", self.s.recv(8))

        # update the virtual latency and remote peer's virtual location
        self.virt_latency = VLPSocket.get_latency(self.virt_loc,
                                                  server_virt_loc)
        self.peer_virt_loc = server_virt_loc

        # update VLP state
        vlpstate.update_peer_location(self.s, self.peer_virt_loc)

        # generate an event
        if event_q:
            event_q.put((Event.CONNECT, self.virt_loc, server_virt_loc))

    def sendall(self, data: bytes) -> None:
        """Lazily send out some data."""
        self.s.sendall(b"")  # check for errors
        self.latest_lt = LazyTransmitter(data, self.s, self.virt_latency,
                                         self.latest_lt)
        self.latest_lt.start()

        # generate an event
        if event_q:
            event_q.put((Event.TRANSMIT, self.virt_loc, self.peer_virt_loc,
                         len(data)))

    def recv(self, bufsize: int) -> bytes:
        """Receive some data."""
        return self.s.recv(bufsize)

    def recv_exact(self, n: int) -> bytes:
        """Keep waiting until `n` bytes have been received."""
        to_recv = n
        result = []
        while to_recv > 0:
            tmp = self.recv(to_recv)
            assert tmp
            to_recv -= len(tmp)
            result.append(tmp)

        return b"".join(result)

    def settimeout(self, value: int) -> None:
        """Set this socket timeout value."""
        self.s.settimeout(value)

    def close(self) -> None:
        """Close this socket."""
        self.s.close()
        if vlpstate.remove_socket(self.s):
            if event_q:
                event_q.put((Event.CLOSE_SOCKET, self.virt_loc,
                             self.peer_virt_loc))

    @staticmethod
    def get_latency(virt_loc1: Location, virt_loc2: Location) -> float:
        """Return the latency of a connection between 2 virtual locations."""
        x1, y1 = virt_loc1
        x2, y2 = virt_loc2
        distance = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
        return distance / PROPAGATION_SPEED
