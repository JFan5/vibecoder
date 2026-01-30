"""Tests for the verification module."""

import pytest
from vibecoder.verification.runner import CommandRunner, CommandResult
from vibecoder.verification.parser import OutputParser, TestFramework
from vibecoder.verification.feedback import FeedbackGenerator


class TestCommandResult:
    """Test cases for CommandResult."""

    def test_success(self):
        """Test success property."""
        result = CommandResult(
            command="echo hello",
            exit_code=0,
            stdout="hello\n",
            stderr="",
        )
        assert result.success is True

    def test_failure(self):
        """Test failure detection."""
        result = CommandResult(
            command="exit 1",
            exit_code=1,
            stdout="",
            stderr="error",
        )
        assert result.success is False

    def test_timeout(self):
        """Test timeout detection."""
        result = CommandResult(
            command="sleep 100",
            exit_code=-1,
            stdout="",
            stderr="",
            timed_out=True,
        )
        assert result.success is False
        assert result.timed_out is True

    def test_output(self):
        """Test combined output."""
        result = CommandResult(
            command="cmd",
            exit_code=1,
            stdout="output",
            stderr="error",
        )
        output = result.output
        assert "output" in output
        assert "STDERR" in output
        assert "error" in output


class TestOutputParser:
    """Test cases for OutputParser."""

    def test_detect_pytest(self):
        """Test pytest detection."""
        parser = OutputParser()
        output = """
============================= test session starts ==============================
collected 5 items

test_foo.py::test_one PASSED
test_foo.py::test_two FAILED

========================= 1 failed, 4 passed in 0.12s =========================
"""
        result = parser.parse(output, 1)
        assert result.framework == TestFramework.PYTEST

    def test_parse_pytest(self):
        """Test pytest output parsing."""
        parser = OutputParser()
        output = """
============================= test session starts ==============================
test_foo.py::test_one PASSED
test_foo.py::test_two PASSED
test_foo.py::test_three FAILED
test_foo.py::test_four PASSED

FAILED test_foo.py::test_three - AssertionError: expected 5

========================= 1 failed, 3 passed in 0.12s =========================
"""
        result = parser.parse(output, 1)

        assert result.passed_tests == 3
        assert result.failed_tests == 1
        assert result.total_tests == 4
        assert not result.success

    def test_parse_generic_success(self):
        """Test generic command success."""
        parser = OutputParser()
        output = "Build successful"

        result = parser.parse(output, 0)

        assert result.framework == TestFramework.UNKNOWN
        assert result.success
        assert result.passed_tests == 1

    def test_parse_generic_failure(self):
        """Test generic command failure."""
        parser = OutputParser()
        output = "Error: something went wrong"

        result = parser.parse(output, 1)

        assert result.framework == TestFramework.UNKNOWN
        assert not result.success
        assert result.failed_tests == 1

    def test_extract_error_locations_python(self):
        """Test extracting Python error locations."""
        parser = OutputParser()
        output = '''
Traceback (most recent call last):
  File "/path/to/file.py", line 42, in test_func
    assert result == expected
AssertionError
'''
        locations = parser.extract_error_locations(output)

        assert len(locations) >= 1
        assert locations[0]["file"] == "/path/to/file.py"
        assert locations[0]["line"] == 42


class TestFeedbackGenerator:
    """Test cases for FeedbackGenerator."""

    def test_generate_all_passed(self):
        """Test feedback when all tests pass."""
        generator = FeedbackGenerator()
        results = [
            CommandResult("pytest", 0, "all passed", ""),
        ]

        feedback = generator.generate(results)

        assert "passed" in feedback.summary.lower()
        assert len(feedback.details) == 0

    def test_generate_failure(self):
        """Test feedback on failure."""
        generator = FeedbackGenerator()
        results = [
            CommandResult("pytest", 1, "FAILED test_one", ""),
        ]

        feedback = generator.generate(results)

        assert "failed" in feedback.summary.lower()
        assert len(feedback.details) > 0

    def test_generate_timeout(self):
        """Test feedback on timeout."""
        generator = FeedbackGenerator()
        results = [
            CommandResult("pytest", -1, "", "", timed_out=True),
        ]

        feedback = generator.generate(results)

        assert "timed out" in feedback.details[0].lower()

    def test_suggestions_import_error(self):
        """Test suggestions for import errors."""
        generator = FeedbackGenerator()
        results = [
            CommandResult(
                "pytest",
                1,
                "ImportError: No module named 'foo'",
                "",
            ),
        ]

        feedback = generator.generate(results)

        # Should suggest checking imports
        import_suggestion = any(
            "import" in s.lower() for s in feedback.suggestions
        )
        assert import_suggestion

    def test_to_text(self):
        """Test converting feedback to text."""
        generator = FeedbackGenerator()
        results = [
            CommandResult("pytest", 1, "test failed", ""),
        ]

        feedback = generator.generate(results)
        text = feedback.to_text()

        assert "Verification Failed" in text
        assert "Summary" in text
        assert "Raw Output" in text
