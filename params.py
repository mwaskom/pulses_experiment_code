from __future__ import division
from copy import deepcopy


# --------------------------------------------------------------------- #
# Base parameters
# --------------------------------------------------------------------- #


base = dict(

    experiment_name="pulses",

    # Display setup
    monitor_name="mlw-mbair",
    fmri_monitor_name="cni_47",
    screen_number=0,
    fmri_screen_number=0,
    monitor_units="deg",
    full_screen=True,
    window_color=0,

    # Fixation
    fix_size=.3,
    fix_iti_color=(0, 0, 0),
    fix_stim_color=(1, 1, -1),
    fix_ready_color=(1, 1, -1),
    fix_pause_color=(1, 1, -1),
    fix_delay_color=(1, 1, -1),
    fix_resp_color=(0, 0, 0),
    fix_fb_colors=[(1, 0, 0), (0, .75, 0)],

    # Response settings
    quit_keys=["escape", "q"],
    ready_keys=["lshift", "rshift"],
    wait_keys=["space"],
    finish_keys=["return"],
    trigger_keys=["quoteleft"],
    resp_keys=["lshift", "rshift"],
    fmri_resp_keys=["4", "9"],

    # Stimulus parameters
    stim_radius=3,
    stim_tex="sin",
    stim_sf=3,
    stim_mask="raisedCos",
    stim_gratings=10,
    stim_speed=1,
    stim_positions=[(-5, 0), (5, 0)],

    # Stimulus contrast parameters
    contrast_pedestal=.2,
    contrast_limits=(.1, .3),
    contrast_deltas=[0, .005, .01, .02, .04, .08],
    contrast_sd=.02,

    # Timing parameters
    orient_dur=0,
    post_stim_dur=0,
    resp_dur=10,
    feedback_dur=.4,
    iti_dur=("uniform", .2, .4),
    after_break_dur=2,

    # Communication
    setup_text_size=.5,

    instruct_text=(
        "Press space to begin the experiment",
    ),

    break_text=(
        "Press space to start the next block",
    ),

    finish_text=(
        "Run Finished!",
    ),

    # Progress bar shown during breaks
    prog_bar_width=5,
    prog_bar_height=.25,
    prog_bar_position=-3,
    prog_bar_linewidth=2,
    prog_bar_color="white",

    # Parameters for plotting performance after each run
    show_performance_plots=True,

    )


training_no_gaps = deepcopy(base)
training_no_gaps.update(

    log_base="data/{subject}_training_no_gaps_run{run:02d}",

    trial_dur=("expon", .2, .6),  # In seconds
    pulse_duration=.2,  # In seconds
    pulse_gap=0,  # In seconds; can be 0

    self_paced=True,

    trials_per_run=600,
    trials_per_break=700,

)


training_with_gaps = deepcopy(base)
training_with_gaps.update(

    log_base="data/{subject}_training_with_gaps_run{run:02d}",

    trial_dur=("truncexpon", 3, 4, 4),  # In seconds
    pulse_duration=.2,  # In seconds
    pulse_gap=("expon", .6, 2),  # In seconds; can be 0

    self_paced=True,

    trials_per_run=60,
    trials_per_break=100,

)
