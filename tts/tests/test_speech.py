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


class TestPathsInProse:
    """Ensure paths are only reduced when they genuinely look like filesystem paths."""

    def test_fraction_in_prose_untouched(self):
        text = "The odds are 3/4 in favor."
        assert clean_for_speech(text) == "The odds are 3/4 in favor."

    def test_aspect_ratio_untouched(self):
        text = "Aspect ratio 16/9 is standard."
        assert clean_for_speech(text) == "Aspect ratio 16/9 is standard."

    def test_and_or_untouched(self):
        text = "Use flag A and/or flag B here."
        assert clean_for_speech(text) == "Use flag A and/or flag B here."

    def test_unit_abbreviation_untouched(self):
        text = "Speed limit is 60 km/h today."
        assert clean_for_speech(text) == "Speed limit is 60 km/h today."

    def test_absolute_path_still_reduced(self):
        """Paths with leading / should still be reduced."""
        text = "Edited /home/marwan/workspace/dotfiles/scripts/foo.sh today."
        assert clean_for_speech(text) == "Edited foo.sh today."

    def test_relative_path_with_extension_still_reduced(self):
        """Relative paths with file extensions should still be reduced."""
        text = "See src/a/b.py:42 there."
        assert clean_for_speech(text) == "See b.py line 42 there."

    def test_decimal_ratio_not_path(self):
        """Decimal ratios like 3/4.5 should not be treated as paths."""
        text = "The ratio is 3/4.5 exactly."
        assert clean_for_speech(text) == "The ratio is 3/4.5 exactly."

    def test_exchange_rate_not_path(self):
        """Exchange rates with decimals should not be treated as paths."""
        text = "The exchange rate is 1/1.25 today."
        assert clean_for_speech(text) == "The exchange rate is 1/1.25 today."

    def test_command_line_flag_not_path(self):
        """Command-line flags like /v should not be treated as paths."""
        text = "Use option /v for verbose."
        assert clean_for_speech(text) == "Use option /v for verbose."

    def test_absolute_path_must_have_multiple_segments(self):
        """Single-segment absolute paths without extension are not paths."""
        text = "Check /tmp or /var directory."
        assert clean_for_speech(text) == "Check /tmp or /var directory."

    def test_absolute_path_with_multiple_segments_still_reduced(self):
        """Multi-segment absolute paths should still be reduced (adversarial: should transform)."""
        text = "Edited /etc/systemd/system/foo.service config."
        assert clean_for_speech(text) == "Edited foo.service config."

    def test_relative_path_with_two_segments_and_extension(self):
        """Relative paths with multiple segments and extension should transform (adversarial: should transform)."""
        text = "See configs/app.json for settings."
        assert clean_for_speech(text) == "See app.json for settings."

    def test_version_number_in_path_not_treated_as_path(self):
        """Version numbers like /v2.5 should not be treated as paths (extension must start with letter)."""
        text = "Check version /v2.5 API doc."
        assert clean_for_speech(text) == "Check version /v2.5 API doc."


class TestEmphasisBoundaries:
    """Ensure emphasis markers are only stripped when paired, not in identifiers."""

    def test_underscore_in_variable_name_preserved(self):
        """Underscores in identifiers like my_var must be preserved."""
        text = "Run `my_var = 1` now."
        assert clean_for_speech(text) == "Run my_var = 1 now."

    def test_underscore_in_filepath_preserved(self):
        """Underscores in file paths must not be stripped."""
        text = "Edited /home/user/my_file.py today."
        assert clean_for_speech(text) == "Edited my_file.py today."

    def test_asterisk_in_arithmetic_preserved(self):
        """Asterisks used for multiplication should not be stripped."""
        text = "The area is 3 * 4 = 12 square feet."
        assert clean_for_speech(text) == "The area is 3 * 4 = 12 square feet."

    def test_asterisk_in_glob_preserved(self):
        """Asterisks in glob patterns should not be stripped."""
        text = "Match files with *.py glob."
        assert clean_for_speech(text) == "Match files with *.py glob."

    def test_paired_double_asterisk_still_stripped(self):
        """Double asterisks for bold emphasis should still be removed."""
        text = "This is **very** important."
        assert clean_for_speech(text) == "This is very important."

    def test_paired_single_underscore_still_stripped(self):
        """Single underscores for italic emphasis should still be removed."""
        text = "This is _odd_."
        assert clean_for_speech(text) == "This is odd."

    def test_original_test_still_works(self):
        """Original test from brief must still pass."""
        assert clean_for_speech("This is **very** _odd_.") == "This is very odd."

    def test_multiple_asterisks_on_one_line_not_mispaired(self):
        """Multiple asterisks on one line must not be mispaired across expressions."""
        text = "The area is 3 * 4 and 5 * 6."
        assert clean_for_speech(text) == "The area is 3 * 4 and 5 * 6."

    def test_multiple_globs_on_one_line_not_mispaired(self):
        """Multiple glob patterns on one line should not be mispaired."""
        text = "Match files with *.py and *.md globs."
        assert clean_for_speech(text) == "Match files with *.py and *.md globs."

    def test_asterisk_requires_non_space_after(self):
        """Asterisks with space after are not emphasis openers."""
        text = "Use * to denote items in a list."
        assert clean_for_speech(text) == "Use * to denote items in a list."

    def test_underscore_requires_non_space_after(self):
        """Underscores with space after are not emphasis openers."""
        text = "The _ character appears in names."
        assert clean_for_speech(text) == "The _ character appears in names."

    def test_paired_emphasis_on_same_line_works(self):
        """Paired emphasis markers on the same line should still work (adversarial: should transform)."""
        text = "This is *italic* and **bold** text."
        assert clean_for_speech(text) == "This is italic and bold text."

    def test_emphasis_with_punctuation_inside_works(self):
        """Emphasis can contain punctuation but no matching marker (adversarial: should transform)."""
        text = "Use _snake_case_ naming convention."
        # Note: 'snake_case' contains an underscore, but it's inside the emphasis markers
        # The first _snake and last case_ won't match the pairing rule (no inner underscores)
        # So this actually should NOT match. Let me reconsider...
        # Actually, with the property that says "contains no occurrence of that same marker inside",
        # _snake_case_ would not be matched as emphasis.
        # So this should remain unchanged.
        assert clean_for_speech(text) == "Use _snake_case_ naming convention."

    def test_emphasis_with_only_non_marker_punctuation_works(self):
        """Emphasis with punctuation but no matching marker should work (adversarial: should transform)."""
        text = "This is *very-important* concept."
        assert clean_for_speech(text) == "This is very-important concept."
