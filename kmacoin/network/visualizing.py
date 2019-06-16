from multiprocessing import Queue
from queue import Empty

import math
import time

# The interval between two consecutive frames:
FRAME_INTERVAL = 20  # in milliseconds

# The number of frames to produce an action:
FRAMES_PER_ACTION = 20

# Timeout value when wait for an event
MAX_UNRESPONSIVE_DURATION = 1

# The radius of a circle representing a node:
CIRCLE_RADIUS = 0.3

# The default color of a circle:
DEFAULT_CIRCLE_COLOR = (0, 0, 1)

# The default color of a line:
DEFAULT_LINE_COLOR = (0, 0, 0)

# The default color of a circle:
DEFAULT_PACKET_COLOR = (1, 0, 0)

# The radius of a circle representing a 1-byte packet:
SMALLEST_PACKET_RADIUS = 0.07

# How fast a packet is transferred?
PROPAGATION_SPEED = 10  # unit distance/second
PACKET_SPEED = PROPAGATION_SPEED / 1000 * FRAME_INTERVAL  # unit distance/frame
SPEED_FACTOR = 1.2
SPEED_FACTOR_UPDATE_START_TIME: float
SPEED_FACTOR_UPDATE_START_FRAME: int


class Event(object):
    """This class acts as a namespace for network event types."""
    CREATE_SOCKET = 0
    CONNECT = 1
    TRANSMIT = 2
    CLOSE_SOCKET = 3


def visualize(event_q: Queue) -> None:
    """
    Visualize network events.

    Notes:
        This function will be executed in another process.

    Args:
        event_q: a queue where network events come from.

    """
    import matplotlib as mpl
    import matplotlib.pyplot as plt
    import matplotlib.animation as animation
    import matplotlib.lines as lines
    mpl.rcParams['toolbar'] = 'None'

    # setup some plotting properties
    plt.figure(num="Network activities")
    plt.grid()
    plt.xlim(0, PROPAGATION_SPEED)
    plt.ylim(0, PROPAGATION_SPEED)

    # nodes/links containers
    current_circles = {}  # location -> [circle, socket_count, label]
    current_lines = {}  # (2 ending-locations) -> [line, line_count]
    current_packets = {}  # (2 ending-locations) -> packet_size

    # objects in animation state
    appearing_circles = {}  # circle -> frame_count
    disappearing_circles = {}  # circle -> frame_count
    appearing_lines = {}  # line -> [vector, frame_count]
    disappearing_lines = {}  # line -> frame_count
    moving_circles = {}  # circle -> [vector, frames_needed, frame_count]

    # current status
    active = False

    def is_active():
        """Return True if there is an object in action."""
        if (len(appearing_circles) == 0 and len(disappearing_circles) == 0 and
                len(appearing_lines) == 0 and len(disappearing_lines) == 0 and
                len(moving_circles) == 0 and len(current_packets) == 0):
            return False
        else:
            return True

    def update_appearing_circles():
        """Update the states of appearing circles."""

        animation_done_circles = []

        # for each circle
        for circle, frame_count in appearing_circles.items():

            # done when enough frames have passed
            if frame_count == FRAMES_PER_ACTION:
                animation_done_circles.append(circle)
                continue

            # increase the circle's radius
            circle.set_radius(frame_count * CIRCLE_RADIUS / FRAMES_PER_ACTION)

            # update the number of frames have passed
            appearing_circles[circle] = frame_count + 1

        # remove animation-done circles
        for circle in animation_done_circles:
            del appearing_circles[circle]

    def update_disappearing_circles():
        """Update the states of disappearing circles."""

        animation_done_circles = []

        # for each circle
        for circle, frame_count in disappearing_circles.items():

            # done when enough frames have passed
            if frame_count == FRAMES_PER_ACTION:
                animation_done_circles.append(circle)
                continue

            # decrease the circle's alpha
            r, g, b, a = circle.get_facecolor()
            a = 1.0 - frame_count / FRAMES_PER_ACTION
            circle.set_facecolor((r, g, b, a))

            # update the number of frames have passed
            disappearing_circles[circle] = frame_count + 1

        # remove animation-done circles
        for circle in animation_done_circles:
            del disappearing_circles[circle]
            circle.remove()

    def update_appearing_lines():
        """Update the states of appearing lines."""

        animation_done_lines = []

        # for each line
        for line, ((dx, dy), frame_count) in appearing_lines.items():

            # done when enough frames have passed
            if frame_count == FRAMES_PER_ACTION:
                animation_done_lines.append(line)
                continue

            # increase the line's length
            (x1, x2), (y1, y2) = line.get_data()
            line.set_data([x1, x2 + dx], [y1, y2 + dy])

            # update the number of frames have passed
            appearing_lines[line][1] = frame_count + 1

        # remove animation-done lines
        for line in animation_done_lines:
            del appearing_lines[line]

    def update_disappearing_lines():
        """Update the states of disappearing lines."""

        animation_done_lines = []

        # for each line
        for line, frame_count in disappearing_lines.items():

            # done when enough frames have passed
            if frame_count == FRAMES_PER_ACTION:
                animation_done_lines.append(line)
                continue

            # switch the line's color
            if frame_count % 2 == 0:
                line.set_color("w")
            else:
                line.set_color(DEFAULT_LINE_COLOR)

            # update the number of frames have passed
            disappearing_lines[line] = frame_count + 1

        # remove animation-done lines
        for line in animation_done_lines:
            del disappearing_lines[line]
            line.remove()

    def update_moving_circles():
        """Update the states of moving circles."""

        # get pending packets
        nonlocal current_packets
        for ((x1, y1), (x2, y2)), size in current_packets.items():
            distance = math.sqrt((x2-x1)**2 + (y2-y1)**2)
            frames_needed = max(1, int(
                distance / (PACKET_SPEED * SPEED_FACTOR)))
            vector = (x2-x1)/frames_needed, (y2-y1)/frames_needed
            circle = plt.Circle(
                xy=(x1, y1),
                radius=size**(1/3) * SMALLEST_PACKET_RADIUS,
                facecolor=DEFAULT_PACKET_COLOR,
            )
            plt.gca().add_artist(circle)
            moving_circles[circle] = [vector, frames_needed, 0]

        # empty the set of pending packets
        current_packets = {}

        # update moving circles
        animation_done_circles = []
        for circle, ((dx, dy), frames_needed, frame_count) in \
                moving_circles.items():

            # done if enough frames have passed
            if frame_count == frames_needed:
                animation_done_circles.append(circle)
                continue

            # moving the circle
            x, y = circle.center
            circle.set_center((x + dx, y + dy))

            # update the number of frames have passed
            moving_circles[circle][2] = frame_count + 1

        # remove animation-done circles
        for circle in animation_done_circles:
            del moving_circles[circle]
            disappearing_circles[circle] = FRAMES_PER_ACTION // 2

    def process_create_socket(args):
        """Process a CREATE_SOCKET event."""

        # get the location
        x, y = location = args[0]
        name = args[1]

        # new-location case:
        if location not in current_circles:

            # make a new circle and add to map
            circle = plt.Circle(xy=location, radius=0.0,
                                facecolor=DEFAULT_CIRCLE_COLOR)
            plt.gca().add_artist(circle)
            label = plt.gca().text(x + CIRCLE_RADIUS, y + CIRCLE_RADIUS, name)
            current_circles[location] = [circle, 1, label]

            # start the creating-node animation
            appearing_circles[circle] = 0

        # already-seen location case:
        else:

            # update `socket_count`
            current_circles[location][1] += 1

    def process_close_socket(args):
        """Process a CLOSE-SOCKET event."""

        # get the location
        loc1, loc2 = args

        # last socket case
        if current_circles[loc1][1] == 1:

            # remove circle
            circle, _, label = current_circles[loc1]
            del current_circles[loc1]

            # start the removing-node animation
            disappearing_circles[circle] = 0
            label.remove()

        else:
            # update `socket_count`
            current_circles[loc1][1] -= 1

        # return now if the socket isn't connected to any address
        if not loc2:
            return

        # last link case
        if current_lines[(loc1, loc2)][1] == 1:

            # remove line
            line = current_lines[(loc1, loc2)][0]
            del current_lines[(loc1, loc2)]

            # start the removing-link animation
            disappearing_lines[line] = 0

        else:
            # update `line_count`
            current_lines[(loc1, loc2)][1] -= 1

    def process_connect(args):
        """Process a CONNECT event."""

        # get the locations
        loc1, loc2 = args
        x1, y1 = loc1
        x2, y2 = loc2

        # new link case:
        if (loc1, loc2) not in current_lines:

            # make a new line and add to map
            line = lines.Line2D(xdata=[x1, x1], ydata=[y1, y1],
                                color=DEFAULT_LINE_COLOR)
            current_lines[(loc1, loc2)] = [line, 1]
            plt.gca().add_line(line)

            # start the creating-link animation
            vector = ((x2 - x1)/FRAMES_PER_ACTION, (y2 - y1)/FRAMES_PER_ACTION)
            appearing_lines[line] = [vector, 0]

        # already-seen link case:
        else:
            current_lines[(loc1, loc2)][1] += 1

    def process_transmit(args):
        """Process a TRANSMIT event."""

        # get the locations and packet size
        loc1, loc2, size = args

        # update `current_packets`
        nonlocal current_packets
        if (loc1, loc2) in current_packets:
            current_packets[(loc1, loc2)] += size
        else:
            current_packets[(loc1, loc2)] = size

    def run(current_frame):
        nonlocal active
        global SPEED_FACTOR_UPDATE_START_TIME, SPEED_FACTOR_UPDATE_START_FRAME
        global SPEED_FACTOR

        # return at first frame to plot a window
        if current_frame == 0:
            return

        # get and process new events
        while True:
            try:
                event_type, *args = event_q.get(timeout=(0 if active else
                                                MAX_UNRESPONSIVE_DURATION))

                if event_type == Event.CREATE_SOCKET:
                    process_create_socket(args)
                elif event_type == Event.CLOSE_SOCKET:
                    process_close_socket(args)
                elif event_type == Event.CONNECT:
                    process_connect(args)
                elif event_type == Event.TRANSMIT:
                    process_transmit(args)

                # from inactive to active -> start measuring time
                if not active and is_active():
                    active = True
                    SPEED_FACTOR_UPDATE_START_TIME = time.time()
                    SPEED_FACTOR_UPDATE_START_FRAME = current_frame

            except Empty:
                if not active:  # return to handle window events
                    return
                else:  # handle animation before return
                    break

        # update in-motion objects
        update_appearing_circles()
        update_disappearing_circles()
        update_appearing_lines()
        update_disappearing_lines()
        update_moving_circles()

        # from active to inactive -> update packet speed
        if not is_active():
            active = False
            current_time = time.time()
            observed = current_time - SPEED_FACTOR_UPDATE_START_TIME
            expected = ((current_frame - SPEED_FACTOR_UPDATE_START_FRAME)
                        * FRAME_INTERVAL / 1000)
            SPEED_FACTOR = observed / expected

    # start the show
    global ani
    ani = animation.FuncAnimation(plt.gcf(), run, interval=FRAME_INTERVAL)
    plt.show()
