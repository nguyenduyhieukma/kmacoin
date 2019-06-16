from kmacoin.globaldef.hash import HASH_OF_NULL
from kmacoin.atnode.node import Node

from multiprocessing import Queue, Process
from queue import Empty
from threading import Thread
from typing import List, Tuple, Dict

Color = Tuple[float, float, float, float]

# The interval between two consecutive frames:
FRAME_INTERVAL = 20  # in milliseconds

# The number of frames to produce an action:
FRAMES_PER_ACTION = 20

# Timeout value when wait for a block
MAX_UNRESPONSIVE_DURATION = 1

# The size of a rectangle representing a block in the block tree:
RECT_WIDTH = 0.5
RECT_HEIGHT = 0.5


def visualize(block_q: Queue, node_name: str):
    """
    Visualize the node's block tree.

    Notes:
        This function will be executed in another process.

    Args:
        block_q: a queue where blocks come from.
        node_name: the name of the node which sends us blocks.

    """
    import matplotlib as mpl
    import matplotlib.pyplot as plt
    import matplotlib.animation as animation
    import matplotlib.lines as lines
    mpl.rcParams['toolbar'] = 'None'

    # setup some plotting properties
    plt.figure(num="The block tree view from node {}".format(node_name))
    plt.grid()
    plt.xlim(-RECT_WIDTH/2, 10 + RECT_WIDTH/2)
    plt.ylim(-5, 5)
    plt.tick_params(left=False, bottom=False, labelleft=False,
                    labelbottom=False)

    # data container
    coords: Dict[bytes, Tuple[int, int]] = {HASH_OF_NULL: (-1, 0)} \
        # block id -> (x,y)
    occupied_ys: List[List[int]] = []  # x-coordinate -> occupied y-coordinates
    owners: List = []
    rects: List = []
    block_counts: List = []
    colors = "grcmykb"

    # objects in animation state
    appearing_rects = {}  # rect -> frame_count
    appearing_lines = {}  # line -> [vector, frame_count]

    # current status
    active = False

    def find_xy(prev_xy):
        """Find an appropriate position for a new block, given its previous
        block's position."""
        prev_x, prev_y = prev_xy
        x = prev_x + 1
        if len(occupied_ys) == x:
            occupied_ys.append([])
        ys = occupied_ys[x]

        delta = 0
        while True:
            y1 = prev_y + delta
            y2 = prev_y - delta

            if prev_y > 0:
                # prioritize y2
                if y2 not in ys:
                    y = y2
                    break
                if y1 not in ys:
                    y = y1
                    break

            else:
                # prioritize y1
                if y1 not in ys:
                    y = y1
                    break
                if y2 not in ys:
                    y = y2
                    break

            delta += 1

        occupied_ys[x].append(y)
        return x, y

    def update_appearing_lines():
        """Update the state of appearing lines"""
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

    def update_appearing_rects():
        """Update the states of appearing rectangles."""

        animation_done_rects = []

        # for each circle
        for rect, frame_count in appearing_rects.items():

            # done when enough frames have passed
            if frame_count == FRAMES_PER_ACTION:
                animation_done_rects.append(rect)
                continue

            # increase the rect's height
            rect.set_height(frame_count * RECT_HEIGHT / FRAMES_PER_ACTION)

            # update the number of frames have passed
            appearing_rects[rect] = frame_count + 1

        # remove animation-done rects
        for rect in animation_done_rects:
            del appearing_rects[rect]

    def is_active():
        """Return True if there is an object in action."""
        if len(appearing_lines) == 0 and len(appearing_rects) == 0:
            return False
        else:
            return True

    def run(current_frame):
        nonlocal active

        # return at first frame to plot a window
        if current_frame == 0:
            return

        # get and process new blocks
        while True:
            try:
                block_id, prev_id, owner = block_q.get(
                    timeout=(0 if active else MAX_UNRESPONSIVE_DURATION))

                prev_x, prev_y = coords[prev_id]
                x, y = find_xy((prev_x, prev_y))
                coords[block_id] = (x, y)

                rect = plt.Rectangle((x - RECT_WIDTH/2, y - RECT_HEIGHT/2),
                                     RECT_WIDTH, RECT_HEIGHT)
                line = lines.Line2D([x - RECT_WIDTH/2] * 2, [y] * 2)
                plt.gca().add_artist(rect)
                plt.gca().add_line(line)

                if owner not in owners:
                    owners.append(owner)
                    rect.set_facecolor(colors[(len(owners)-1) % len(colors)])
                    rects.append(rect)
                    block_counts.append(1)

                else:
                    index = owners.index(owner)
                    block_counts[index] += 1
                    rect.set_facecolor(colors[index % len(colors)])

                plt.legend(
                    rects,
                    ['{}: {}'.format(owner[:6], block_count) for
                     owner, block_count in zip(owners, block_counts)],
                    prop={"family": "monospace"}
                )

                lower_xlim, upper_xlim = plt.gca().get_xlim()
                if upper_xlim < x + RECT_WIDTH:
                    plt.xlim((lower_xlim, upper_xlim*2 - RECT_WIDTH/2))

                appearing_rects[rect] = 0
                appearing_lines[line] = [(
                    - (x - prev_x - RECT_WIDTH) / FRAMES_PER_ACTION,
                    - (y - prev_y) / FRAMES_PER_ACTION
                ), 0]

                # switch to active
                active = True

            except Empty:
                if not active:  # return to handle window events
                    return
                else:  # handle animation before return
                    break

        # update in-motion objects
        update_appearing_lines()
        update_appearing_rects()

        # switch to inactive if there is no object in action
        if not is_active():
            active = False

    # start the show
    global ani
    ani = animation.FuncAnimation(plt.gcf(), run, interval=FRAME_INTERVAL)
    plt.show()


class BlockVisualizer(Thread):
    """This class represents a visualizer."""
    def __init__(self, node: Node):
        super().__init__()
        self.node = node

    def run(self):
        # synchronize
        with self.node.block_tree_lock:
            self.node.vis_block_q = Queue()
            for block_id in self.node.block_tree.traverse():
                if block_id == HASH_OF_NULL:
                    continue
                block = self.node.load_block(block_id)
                self.node.vis_block_q.put((
                    block_id,
                    block.prev_id,
                    block.txs[0].outputs[0].owner.hex()
                ))

        # start visualizing in a new process, then block current thread
        visualizer = Process(target=visualize,
                             args=(self.node.vis_block_q, self.node.name))
        visualizer.start()
        visualizer.join()

        # visualizing has stopped, remove `vis_block_q`
        self.node.vis_block_q = None
