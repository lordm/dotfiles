-- Low-latency ALSA config for Focusrite Scarlett Solo 4th Gen
--
-- NOTE: table.insert, NOT `alsa_monitor.rules = {...}`. This file loads after
-- /usr/share/wireplumber/main.lua.d/50-alsa-config.lua, so a plain assignment
-- REPLACES WirePlumber's shipped default rules instead of extending them. That
-- silently discarded api.alsa.use-acp / api.acp.auto-profile / api.acp.auto-port
-- for EVERY card on the machine, not just this one: ALSA card profiles and ports
-- disappeared system-wide, which killed jack sensing on the built-in ALC257
-- (headphone amp stuck muted with no port to select it) and exposed all four
-- NVIDIA HDMI PCMs as sinks with no availability tracking.
--
-- The Scarlett itself is driven from the `pro-audio` profile, which maps straight
-- to raw hw:2,0. Note ACP ranks pro-audio at priority 1 (lowest), so it is NOT
-- auto-selected -- it is pinned in ~/.local/state/wireplumber/default-profile.
-- Without that, ACP picks output:analog-stereo+input:analog-surround-40, which
-- relabels the card's 4 capture channels as FL/FR/RL/RR through the surround40
-- plug layer.
--
-- The node.name globs below match the middle segment of the node name, which is
-- unaffected by the profile suffix (.pro-output-0 / .analog-stereo / etc).
table.insert(alsa_monitor.rules, {
  matches = {
    {
      { "node.name", "matches", "alsa_output.*Scarlett*" },
    },
    {
      { "node.name", "matches", "alsa_input.*Scarlett*" },
    },
  },
  apply_properties = {
    ["api.alsa.disable-batch"] = true,
    ["api.alsa.headroom"]      = 128,
    ["api.alsa.period-size"]   = 512,
    ["api.alsa.period-num"]    = 2,
    ["session.suspend-timeout-seconds"] = 60,
  },
})
