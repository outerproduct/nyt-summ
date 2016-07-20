#! /usr/bin/env python3
# Author: Kapil Thadani (kapil@cs.columbia.edu)

import logging
import os
import sys
import time


class Timer(object):
    """A convenient class for timing the execution of code snippets.
    - For normal timing, place the code snippet under
            with Timer():
    - For average timing of a loop, initialize with
            with Timer(num_iters):
    - For continuous timing while the loop is running, initialize with
            with Timer(optional_num_iters) as t:
      and call
            t.status(optional_msg)
      within the loop body.
    """
    reset_color = "\033[0m"          # no attributes
    final_color = "\033[38;5;8m"     # fg=grey
    active_color = "\033[38;5;15m"   # bold; fg=white

    def __init__(self, count=None, adapt=True, deactivate=True, newline=True,
                 silent=False, stdout=False):
        """Initialize the timer count for averaging.
        """
        if count is None or (isinstance(count, int) and count > 0):
            self.count = count
        else:
            logging.error("Inappropriate count value {0:d} for Timer"
                          .format(count))
            self.count = None

        # Number of loop iterations, i.e., calls to status().
        self.i = 0

        # Number of iterations to skip when printing status. Useful for when
        # loop iterations are fast and printing to the console is a bottleneck.
        self.skip = 1

        # The last message to be printed to status().
        self.last_message = None

        # Whether to automatically adapt the skip value to prevent delays
        # due to buffering. Writes will be scheduled at approximately 1/sec.
        self.adapt = adapt

        # Whether to display a final timer statement in a low-contrast color
        # on exiting the timer. Set to False when the timer status messages
        # should remain highly visible.
        self.deactivate = deactivate

        # Whether to print a newline on exiting the timer, thereby preventing
        # the previous timer output from being overwritten. Set to False when
        # working with timed code that calls other timed code.
        self.newline = newline

        # Whether to suppress all printing. Set to True to prevent an inner
        # loop timer from clobbering the output of an outer loop timer.
        self.silent = silent

        # The stream to send timer status messages to. By default, these are
        # written to stderr.
        self.stream = sys.stdout if stdout else sys.stderr

    def __enter__(self):
        """Record the start time as the 'with' block is entered.
        """
        self.start = time.time()
        return self

    def __exit__(self, *args):
        """Record the elapsed time as the 'with' block is left and print
        it to the console.
        """
        if self.silent:
            return

        # Print the final timer status
        color = self.final_color if self.deactivate else self.active_color

        if self.i > 1 or self.count is not None:
            num_iters = self.i if self.i > 0 else self.count

            # Display average time elapsed per instance
            self.display("[{0:.2g}s on avg]".format(
                (time.time() - self.start) / num_iters),
                message=self.last_message,
                msg_color=color,
                timing_color=color,
                )
        else:
            # Display total time elapsed
            self.display("[{0:.2g}s]".format(
                time.time() - self.start),
                message=self.last_message,
                msg_color=color,
                timing_color=color,
                )

        # Prevent the final timing string from being overwritten
        if self.newline:
            print(file=self.stream)

    def status(self, message=None):
        """Print a message to the console in addition to the average
        time elapsed and reposition the cursor.
        """
        self.i += 1
        self.last_message = message

        if self.silent:
            return

        if self.skip > 1 and self.i % self.skip != 0:
            return

        if self.adapt:
            # Set skip to the reciprocal of per-instance time to schedule
            # status updates at approximately 1/sec.
            # We use i-1 instead of i to compensate for cases in which
            # status() is called prior to slow processing, resulting in
            # skip getting set to a large value from the outset.
            self.skip = int((self.i - 1) / (time.time() - self.start))

        self.display("[{0:.2g}s{1}]".format(
            (time.time() - self.start) / self.i,
            ' on avg' if self.i > 1 else ''),
            message=str(message) if message is not None else None,
            msg_color=self.active_color,
            timing_color=self.active_color)

    def display(self, timing, message=None, msg_color=None, timing_color=None):
        """Display the given timing string and an optional message on the
        console.
        """
        if msg_color is None:
            msg_color = self.final_color
        if timing_color is None:
            timing_color = self.final_color

        num_cols = int(os.popen('stty size', 'r').read().split()[1])
        max_msg_len = num_cols - len(timing)

        if message is None:
            # No message; entire width available for timing string
            message = ""
            rwidth = num_cols
        elif len(message.expandtabs()) > max_msg_len:
            # Message too long and will be truncated to show timing string
            message = message[:max_msg_len]
            rwidth = len(timing)
        else:
            rwidth = num_cols - len(message.expandtabs())

        # Print and reposition the cursor
        print("{0}{1}{2}{3:>{4:d}s}{5}".format(
              msg_color, message, timing_color,
              timing, rwidth, self.reset_color),
              end='\r', file=self.stream)
