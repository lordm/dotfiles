-- Low-latency ALSA config for Focusrite Scarlett Solo 4th Gen
alsa_monitor.rules = {
  {
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
      ["session.suspend-timeout-seconds"] = 0,
    },
  },
}
