#!/usr/bin/env bash
# Right-hand tmux status payload: agent-tts state, drawn after tmux-status.sh.
#
# Same rule as tmux-status.sh: ONE process. tmux re-runs this on every
# status-interval tick, and again every time the daemon pushes a refresh at the
# start and end of an utterance, so it is bash builtins only. `tts status`
# would be the obvious implementation and is the wrong one -- it forks a Python
# interpreter and round-trips the socket, several times a second while
# something is being spoken. Everything here is a stat of a file the daemon
# maintains, and the paths mirror tts/paths.py so the two cannot disagree.
#
# Liveness is the pid file, NOT the socket. An AF_UNIX socket file outlives the
# process that bound it, and ttsd installs no SIGTERM handler, so after
# `systemctl stop tts.service` the socket is still sitting on disk: the `[ -S ]`
# test this script used to do reported a stopped daemon as running, which is
# exactly the case the indicator exists for. /proc is the only honest answer.
# (A pid recycled onto an unrelated process would read as alive. That needs the
# pid space to wrap between a crash and a glance at the status bar; the cost of
# being wrong is a missing icon, so it is not worth a cmdline check that would
# instead break silently if the unit's ExecStart ever changed.)
#
# Always prints exactly one glyph, so the segment is a fixed two columns wide and
# nothing to its right ever shifts. It sits at the *left* of status-right for the
# same reason: status-right is right-aligned, so a segment that changed width
# there would drag the load figures sideways every time the state changed.
#
# Idle and speaking share the volume_high glyph and differ only in colour: grey
# is a resting state (idle, muted), gold means something wants noticing (audio
# playing right now, or no daemon at all).

runtime_dir=${XDG_RUNTIME_DIR:-/run/user/$UID}
data_dir=${XDG_DATA_HOME:-$HOME/.local/share}/tts

# Material Design glyphs from the Nerd Font patch. Chosen over the equivalent
# FontAwesome ones deliberately: fontconfig resolves these Plane-15 codepoints
# to exactly one installed font, while the U+F0xx block is also claimed by
# Webdings and a couple of legacy CJK fonts -- there, fallback can quietly draw
# a *wrong* glyph, which is worse than an obviously missing one. All three are
# single-width, so the column budget in tmux.conf still holds.
GLYPH_VOLUME=$'\U000F057E'  # md-volume_high -- ready to speak, or speaking now
GLYPH_MUTED=$'\U000F0581'   # md-volume_off  -- silenced by the user
GLYPH_DOWN=$'\U000F0026'    # md-alert       -- no daemon, so nothing narrates
GOLD='#[fg=#D4AF37]'        # brand accent: a state worth noticing
DIM='#[fg=colour245]'       # the same grey as the load/mem segment

alive=
if [[ -r $runtime_dir/tts.pid ]]; then
  read -r pid < "$runtime_dir/tts.pid"
  [[ -n $pid && -d /proc/$pid ]] && alive=1
fi

if [[ -z $alive ]]; then
  printf '%s%s' "$GOLD" "$GLYPH_DOWN"
elif [[ -e $data_dir/muted ]]; then
  printf '%s%s' "$DIM" "$GLYPH_MUTED"
elif [[ -e $runtime_dir/tts.speaking ]]; then
  printf '%s%s' "$GOLD" "$GLYPH_VOLUME"
else
  printf '%s%s' "$DIM" "$GLYPH_VOLUME"
fi
