import pytest
from tts.speech import (
    clean_for_speech, estimate_seconds, cap_to_duration, prepare, split_sentences,
)


class TestCodeBlocks:
    def test_fenced_block_becomes_line_count(self):
        text = "Here is the fix:\n\n```python\na = 1\nb = 2\nc = 3\n```\n\nDone."
        assert clean_for_speech(text) == "Here is the fix: code block, 3 lines. Done."

    def test_fenced_block_singular_line(self):
        text = "```\nrm -rf /\n```"
        assert clean_for_speech(text) == "code block, 1 line."

    def test_unterminated_fence_does_not_swallow_rest(self):
        # A response truncated mid-block must not silently drop everything after it.
        text = "Trying this:\n```python\nx = 1"
        assert clean_for_speech(text) == "Trying this: code block, 1 line."


class TestInlineCode:
    def test_short_inline_code_is_kept_verbatim(self):
        assert clean_for_speech("Run `git status` now.") == "Run git status now."

    def test_long_inline_code_becomes_snippet(self):
        text = "Use `foo(a, b, c, d, e)` here."
        assert clean_for_speech(text) == "Use snippet here."


class TestLinksAndPaths:
    def test_markdown_link_keeps_text(self):
        assert clean_for_speech("See [the docs](https://x.com/y).") == "See the docs."

    def test_bare_url_becomes_a_link(self):
        assert clean_for_speech("See https://example.com/a/b now.") == "See a link now."

    def test_absolute_path_reduced_to_basename(self):
        text = "Edited /home/marwan/workspace/dotfiles/scripts/foo.sh today."
        assert clean_for_speech(text) == "Edited foo.sh today."

    def test_path_with_line_number_keeps_line_number(self):
        assert clean_for_speech("See src/a/b.py:42 there.") == "See b.py line 42 there."


class TestMarkdownStructure:
    def test_headings_lose_markers(self):
        assert clean_for_speech("## Results\n\nAll green.") == "Results. All green."

    def test_emphasis_markers_stripped(self):
        assert clean_for_speech("This is **very** _odd_.") == "This is very odd."

    def test_table_becomes_row_count(self):
        text = "| a | b |\n| --- | --- |\n| 1 | 2 |\n| 3 | 4 |"
        assert clean_for_speech(text) == "a table with 2 rows."

    def test_list_items_joined_with_pauses(self):
        assert clean_for_speech("- first\n- second") == "first. second."

    def test_numbered_list_markers_dropped(self):
        assert clean_for_speech("1. first\n2. second") == "first. second."


class TestWhitespaceAndEmpty:
    def test_whitespace_collapsed(self):
        assert clean_for_speech("a\n\n\n   b") == "a b"

    def test_empty_input_returns_empty(self):
        assert clean_for_speech("") == ""

    def test_whitespace_only_returns_empty(self):
        assert clean_for_speech("   \n\t  ") == ""

    def test_code_block_only_response_still_speaks(self):
        assert clean_for_speech("```\nx\n```") == "code block, 1 line."


class TestDurationAndCap:
    def test_estimate_uses_wpm(self):
        assert estimate_seconds(" ".join(["word"] * 160), wpm=160) == pytest.approx(60.0)

    def test_short_text_is_not_capped(self):
        text = "One. Two. Three."
        assert cap_to_duration(text, max_seconds=45.0) == text

    def test_long_text_truncates_at_sentence_boundary(self):
        long = ". ".join(" ".join(["word"] * 20) for _ in range(20)) + "."
        out = cap_to_duration(long, max_seconds=10.0, wpm=160)
        assert out.endswith("continues on screen.")
        assert len(out.split()) < len(long.split())
        # Truncation must not slice a sentence in half.
        body = out[: -len(" continues on screen.")]
        assert body.endswith(".")

    def test_cap_keeps_at_least_one_sentence(self):
        # A single sentence longer than the cap is still spoken, not blanked.
        one = " ".join(["word"] * 500) + "."
        out = cap_to_duration(one, max_seconds=1.0, wpm=160)
        assert out.startswith("word word")


class TestSentenceSplit:
    def test_splits_on_terminators(self):
        assert split_sentences("One. Two! Three?") == ["One.", "Two!", "Three?"]

    def test_no_terminator_yields_single_chunk(self):
        assert split_sentences("just this") == ["just this"]

    def test_empty_yields_empty_list(self):
        assert split_sentences("") == []


class TestPrepare:
    def test_prepare_cleans_then_caps(self):
        text = "Fixed it.\n\n```py\na\nb\n```\n\nSee /tmp/x/y.log for detail."
        assert prepare(text) == "Fixed it. code block, 2 lines. See y.log for detail."
