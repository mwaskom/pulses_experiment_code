from __future__ import division, print_function
import sys
import itertools

import numpy as np
import pandas as pd

from psychopy import core, visual, event
import cregg
from scdp import StimArray

import warnings
warnings.simplefilter("ignore", FutureWarning)


# =========================================================================== #
# Basic setup
# =========================================================================== #


def main(arglist):

    # Get the experiment parameters
    mode = arglist.pop(0)
    p = cregg.Params(mode)
    p.set_by_cmdline(arglist)

    # Open up the stimulus window
    win = cregg.launch_window(p)
    p.win_refresh_hz = win.refresh_hz

    # Initialize some common visual objects
    stims = cregg.make_common_visual_objects(win, p)

    # Initialize the main stimulus arrays
    stims["patches"] = StimArray(win, p)

    # Execute the experiment function
    globals()[mode](p, win, stims)


# =========================================================================== #
# Helper functions
# =========================================================================== #


def pulse_onsets(p, refresh_hz, trial_flips, rs=None):
    """Return indices for frames where each pulse will start."""
    if rs is None:
        rs = np.random.RandomState()

    # Convert seconds to screen refresh units
    pulse_secs = cregg.flexible_values(p.pulse_duration, random_state=rs)
    pulse_flips = refresh_hz * pulse_secs

    # Schedule the first pulse for the trial onset
    pulse_times = [0]

    # Schedule additional pulses
    while True:

        last_pulse = pulse_times[-1]
        ipi = cregg.flexible_values(p.pulse_gap, random_state=rs)
        ipi_flips = int(np.round(ipi * refresh_hz))
        next_pulse = (last_pulse +
                      pulse_flips +
                      ipi_flips)
        if (next_pulse + pulse_flips) > trial_flips:
            break
        else:
            pulse_times.append(int(next_pulse))

    pulse_times = np.array(pulse_times, np.int)

    return pulse_times


def contrast_schedule(onsets, mean, sd, limits,
                      trial_flips, pulse_flips, rs=None):
    """Return a vector with the contrast on each flip."""
    if rs is None:
        rs = np.random.RandomState()

    contrast_vector = np.zeros(trial_flips)
    contrast_values = []
    for onset in onsets:
        offset = onset + pulse_flips
        while True:
            pulse_contrast = rs.normal(mean, sd)
            if limits[0] <= pulse_contrast <= limits[1]:
                break
        contrast_vector[onset:offset] = pulse_contrast
        contrast_values.append(pulse_contrast)

    return contrast_vector, contrast_values


def generate_contrast_pair(p):
    """Find a valid pair of contrasts (or distribution means).

    Currently not vectorized, but should be...

    """
    rs = np.random.RandomState()
    need_contrasts = True
    while need_contrasts:

        # Determine the "pedestal" contrast
        # Note that this is misleading as it may vary from trial to trial
        # But it makes sense give that our main IV is the delta
        pedestal = np.round(cregg.flexible_values(p.contrast_pedestal), 2)

        # Determine the "variable" contrast
        delta_dir = rs.choice([-1, 1])
        delta = cregg.flexible_values(p.contrast_deltas)
        variable = pedestal + delta_dir * delta

        # Determine the assignment to sides
        contrasts = ((pedestal, variable)
                     if rs.randint(2)
                     else (variable, pedestal))

        # Check if this is a valid pair
        within_limits = (min(contrasts) >= p.contrast_limits[0]
                         and max(contrasts) <= p.contrast_limits[1])
        if within_limits:
            need_contrasts = False

    return contrasts


# =========================================================================== #
# Experiment functions
# =========================================================================== #


def training_no_gaps(p, win, stims):

    design = behavior_design(p)
    behavior(p, win, stims, design)


def training_with_gaps(p, win, stims):

    design = behavior_design(p)
    behavior(p, win, stims, design)


def behavior(p, win, stims, design):

    stim_event = EventEngine(win, p, stims)

    stims["instruct"].draw()

    log_cols = list(design.columns)
    log_cols += ["stim_time",
                 "act_mean_l", "act_mean_r", "act_mean_delta",
                 "pulse_count",
                 "key", "response",
                 "gen_correct", "act_correct", "rt"]

    log = cregg.DataLog(p, log_cols)
    log.pulses = PulseLog()

    with cregg.PresentationLoop(win, p, log, fix=stims["fix"],
                                exit_func=save_pulse_log):

        for t, t_info in design.iterrows():

            if t_info["break"]:

                # Show a progress bar and break message
                stims["progress"].update_bar(t / len(design))
                stims["progress"].draw()
                stims["break"].draw()

            # Start the trial
            stims["fix"].draw()
            win.flip()

            # Wait for the ITI before the stimulus
            cregg.wait_check_quit(t_info["iti"])

            # Build the pulse schedule for this trial
            trial_flips = win.refresh_hz * t_info["trial_dur"]
            pulse_flips = win.refresh_hz * p.pulse_duration

            # Schedule pulse onsets
            trial_onsets = pulse_onsets(p, win.refresh_hz, trial_flips)
            t_info.ix["pulse_count"] = len(trial_onsets)

            # Determine the sequence of stimulus contrast values
            # TODO Improve this by using semantic indexing and not position
            trial_contrast = np.zeros((trial_flips, 2))
            trial_contrast_means = []
            trial_contrast_values = []
            for i, mean in enumerate(t_info[["gen_mean_l", "gen_mean_r"]]):
                vector, values = contrast_schedule(trial_onsets,
                                                   mean,
                                                   p.contrast_sd,
                                                   p.contrast_limits,
                                                   trial_flips,
                                                   pulse_flips)
                trial_contrast[:, i] = vector
                trial_contrast_means.append(np.mean(values))
                trial_contrast_values.append(values)

            # Log some information about the actual values
            act_mean_l, act_mean_r = trial_contrast_means
            t_info.ix["act_mean_l"] = act_mean_l
            t_info.ix["act_mean_r"] = act_mean_r
            t_info.ix["act_mean_delta"] = act_mean_r - act_mean_l

            # Log the pulse-wise information
            log.pulses.update(trial_onsets, trial_contrast_values)

            # Compute the signed difference in the generating means
            contrast_delta = t_info["gen_mean_r"] - t_info["gen_mean_l"]

            # Execute this trial
            res = stim_event(trial_contrast, contrast_delta)

            # Log whether the response agreed with what was actually shown
            res["act_correct"] = (res["response"] ==
                                  (t_info["act_mean_delta"] > 0))

            # Record the result of the trial
            t_info = t_info.append(pd.Series(res))
            log.add_data(t_info)

        stims["finish"].draw()


def save_pulse_log(log):

    if not log.p.nolog:
        fname = log.p.log_base.format(subject=log.p.subject,
                                      run=log.p.run)
        log.pulses.save(fname)


# =========================================================================== #
# Event controller
# =========================================================================== #


class EventEngine(object):
    """Controller object for trial events."""
    def __init__(self, win, p, stims):

        self.win = win
        self.p = p

        self.fix = stims.get("fix", None)
        self.lights = stims.get("patches", None)

        self.break_keys = p.resp_keys + p.quit_keys
        self.ready_keys = p.ready_keys
        self.resp_keys = p.resp_keys
        self.quit_keys = p.quit_keys

        self.clock = core.Clock()
        self.resp_clock = core.Clock()

    def wait_for_ready(self):
        """Allow the subject to control the start of the trial."""
        self.fix.color = self.p.fix_ready_color
        self.fix.draw()
        self.win.flip()
        while True:
            keys = event.waitKeys(np.inf, self.p.ready_keys + self.p.quit_keys)
            for key in keys:
                if key in self.quit_keys:
                    core.quit()
                elif key in self.ready_keys:
                    listen_for = [k for k in self.ready_keys if k != key]
                    next_key = event.waitKeys(.1, listen_for)
                    if next_key is not None:
                        return self.clock.getTime()
                    else:
                        continue

    def collect_response(self, correct_response):
        """Wait for a button press and determine result."""
        # Initialize trial data
        correct = False
        used_key = np.nan
        response = np.nan
        rt = np.nan

        # Put the screen into response mode
        self.fix.color = self.p.fix_resp_color
        self.fix.draw()
        self.win.flip()

        # Wait for the key press
        event.clearEvents()
        self.resp_clock.reset()
        keys = event.waitKeys(self.p.resp_dur,
                              self.break_keys,
                              self.resp_clock)

        # Determine what was pressed
        keys = [] if keys is None else keys
        for key, timestamp in keys:

            if key in self.quit_keys:
                core.quit()

            if key in self.resp_keys:
                used_key = key
                rt = timestamp
                response = self.resp_keys.index(key)
                correct = response == correct_response

        return dict(key=used_key,
                    response=response,
                    gen_correct=correct,
                    rt=rt)

    def __call__(self, contrast_values, contrast_delta, stim_time=None):
        """Execute a stimulus event."""

        # Show the fixation point and wait to start the trial
        if self.p.self_paced:
            stim_time = self.wait_for_ready()
        else:
            self.fix.color = self.p.fix_ready_color
            cregg.precise_wait(self.wi, self.clock, stim_time, self.fix)

        # Frames where the lights can pulse
        for i, frame_contrast in enumerate(contrast_values):

            self.lights.contrast = frame_contrast
            self.lights.draw()
            self.fix.draw()
            self.win.flip()

        # Post stimulus delay
        self.fix.color = self.p.fix_delay_color
        self.fix.draw()
        self.win.flip()
        cregg.wait_check_quit(self.p.post_stim_dur)

        # Response period
        # TODO Given that we are showing feedback based on the generating
        # means and not what actually happens, the concept of "correct" is
        # a little confusing. Rework to specify in terms of feedback valnece
        if contrast_delta == 0:
            correct_response = np.random.choice([0, 1])
        else:
            # 1 here will map to right button press below
            # Probably a safer way to do this...
            correct_response = int(contrast_delta > 0)

        result = self.collect_response(correct_response)
        result["stim_time"] = stim_time

        # Feedback
        self.fix.color = self.p.fix_fb_colors[int(result["gen_correct"])]
        self.fix.draw()
        self.win.flip()

        cregg.wait_check_quit(self.p.feedback_dur)

        # End of trial
        self.fix.color = self.p.fix_iti_color
        self.fix.draw()
        self.win.flip()

        return result


# =========================================================================== #
# Stimulus log control
# =========================================================================== #


class PulseLog(object):

    def __init__(self):

        self.pulse_times = []
        self.contrast_values = []

    def update(self, pulse_times, contrast_values):

        self.pulse_times.append(pulse_times)
        self.contrast_values.append(contrast_values)

    def save(self, fname):

        np.savez(fname,
                 pulse_onsets=self.pulse_times,
                 contrast_values=self.contrast_values)


# =========================================================================== #
# Design functions
# =========================================================================== #


def behavior_design(p):

    columns = ["iti", "trial_dur", "gen_mean_l", "gen_mean_r"]
    iti = cregg.flexible_values(p.iti_dur, p.trials_per_run)
    trial_dur = cregg.flexible_values(p.trial_dur, p.trials_per_run)
    df = pd.DataFrame(dict(iti=iti, trial_dur=trial_dur),
                      columns=columns,
                      dtype=np.float)

    for i in range(p.trials_per_run):
        df.loc[i, ["gen_mean_l", "gen_mean_r"]] = generate_contrast_pair(p)

    df["gen_mean_delta"] = df["gen_mean_r"] - df["gen_mean_l"]

    trial = df.index.values
    df["break"] = ~(trial % p.trials_per_break).astype(bool)
    df.loc[0, "break"] = False

    return df


if __name__ == "__main__":
    main(sys.argv[1:])
