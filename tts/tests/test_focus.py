from tts.focus import is_focused


def q(response):
    """Build a stub query returning a fixed tmux response."""
    return lambda pane_id: response


class TestFocusDecision:
    def test_active_pane_of_attached_session_is_focused(self):
        assert is_focused("%4", q("1,1,1")) is True

    def test_inactive_pane_is_not_focused(self):
        assert is_focused("%2", q("0,0,1")) is False

    def test_active_pane_in_background_window_is_not_focused(self):
        assert is_focused("%6", q("1,0,1")) is False

    def test_active_pane_of_detached_session_is_not_focused(self):
        # tmux session running but nobody is looking at it.
        assert is_focused("%10", q("1,1,0")) is False

    def test_multiple_attached_clients_still_counts(self):
        assert is_focused("%4", q("1,1,2")) is True


class TestNonTmuxAndFailures:
    def test_no_pane_id_is_treated_as_focused(self):
        # claude-desktop and editor integrations run outside tmux entirely.
        assert is_focused(None, q(None)) is True

    def test_empty_pane_id_is_treated_as_focused(self):
        assert is_focused("", q(None)) is True

    def test_dead_pane_is_not_focused(self):
        # Pane closed between the hook firing and the daemon asking.
        assert is_focused("%99", q(None)) is False

    def test_malformed_response_is_not_focused(self):
        assert is_focused("%4", q("garbage")) is False

    def test_short_response_is_not_focused(self):
        assert is_focused("%4", q("1,1")) is False
