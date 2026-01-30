"""Output parsing for verification results."""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class TestFramework(str, Enum):
    """Known test frameworks."""

    PYTEST = "pytest"
    JEST = "jest"
    MOCHA = "mocha"
    UNITTEST = "unittest"
    GO_TEST = "go_test"
    CARGO_TEST = "cargo_test"
    UNKNOWN = "unknown"


@dataclass
class TestResult:
    """Individual test result."""

    name: str
    passed: bool
    error_message: Optional[str] = None
    file_path: Optional[str] = None
    line_number: Optional[int] = None


@dataclass
class ParsedResult:
    """Parsed verification result."""

    framework: TestFramework
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    skipped_tests: int = 0
    error_tests: int = 0
    test_results: list[TestResult] = field(default_factory=list)
    raw_output: str = ""

    @property
    def success(self) -> bool:
        """Check if all tests passed."""
        return self.failed_tests == 0 and self.error_tests == 0

    @property
    def summary(self) -> str:
        """Get a summary string."""
        return (
            f"{self.framework.value}: "
            f"{self.passed_tests} passed, "
            f"{self.failed_tests} failed, "
            f"{self.skipped_tests} skipped"
        )


class OutputParser:
    """Parser for test framework outputs."""

    def parse(self, output: str, exit_code: int) -> ParsedResult:
        """Parse verification output.

        Args:
            output: The combined stdout/stderr output
            exit_code: The command exit code

        Returns:
            ParsedResult with parsed information
        """
        # Try to detect the framework
        framework = self._detect_framework(output)

        if framework == TestFramework.PYTEST:
            return self._parse_pytest(output, exit_code)
        elif framework == TestFramework.JEST:
            return self._parse_jest(output, exit_code)
        elif framework == TestFramework.GO_TEST:
            return self._parse_go_test(output, exit_code)
        elif framework == TestFramework.CARGO_TEST:
            return self._parse_cargo_test(output, exit_code)
        else:
            return self._parse_generic(output, exit_code)

    def _detect_framework(self, output: str) -> TestFramework:
        """Detect which test framework produced the output."""
        if "pytest" in output or "====" in output and "passed" in output:
            return TestFramework.PYTEST
        elif "PASS" in output and "FAIL" in output and "Test Suites:" in output:
            return TestFramework.JEST
        elif "--- PASS:" in output or "--- FAIL:" in output:
            return TestFramework.GO_TEST
        elif "running" in output and "test result:" in output:
            return TestFramework.CARGO_TEST
        return TestFramework.UNKNOWN

    def _parse_pytest(self, output: str, exit_code: int) -> ParsedResult:
        """Parse pytest output."""
        result = ParsedResult(
            framework=TestFramework.PYTEST,
            raw_output=output,
        )

        # Parse summary line - pytest can order these differently
        # Look for individual counts: "N passed", "N failed", "N skipped", "N error"
        passed_match = re.search(r"(\d+) passed", output)
        failed_match = re.search(r"(\d+) failed", output)
        skipped_match = re.search(r"(\d+) skipped", output)
        error_match = re.search(r"(\d+) error", output)

        if passed_match:
            result.passed_tests = int(passed_match.group(1))
        if failed_match:
            result.failed_tests = int(failed_match.group(1))
        if skipped_match:
            result.skipped_tests = int(skipped_match.group(1))
        if error_match:
            result.error_tests = int(error_match.group(1))

        result.total_tests = (
            result.passed_tests
            + result.failed_tests
            + result.skipped_tests
            + result.error_tests
        )

        # Parse individual failures
        failure_pattern = re.compile(
            r"FAILED\s+([\w/\.]+)::(\w+)(?:::(\w+))?\s*-\s*(.+)",
            re.MULTILINE,
        )
        for match in failure_pattern.finditer(output):
            file_path = match.group(1)
            test_name = match.group(3) or match.group(2)
            error_msg = match.group(4)

            result.test_results.append(
                TestResult(
                    name=test_name,
                    passed=False,
                    error_message=error_msg,
                    file_path=file_path,
                )
            )

        return result

    def _parse_jest(self, output: str, exit_code: int) -> ParsedResult:
        """Parse Jest output."""
        result = ParsedResult(
            framework=TestFramework.JEST,
            raw_output=output,
        )

        # Parse summary: "Tests: 2 failed, 3 passed, 5 total"
        summary_match = re.search(
            r"Tests:\s*(?:(\d+) failed,\s*)?(?:(\d+) passed,\s*)?(\d+) total",
            output,
        )
        if summary_match:
            result.failed_tests = int(summary_match.group(1) or 0)
            result.passed_tests = int(summary_match.group(2) or 0)
            result.total_tests = int(summary_match.group(3) or 0)

        # Parse failures
        failure_pattern = re.compile(
            r"✕\s+(.+?)\s*\n.*?Error:\s*(.+?)(?=\n\n|\Z)",
            re.DOTALL,
        )
        for match in failure_pattern.finditer(output):
            result.test_results.append(
                TestResult(
                    name=match.group(1).strip(),
                    passed=False,
                    error_message=match.group(2).strip(),
                )
            )

        return result

    def _parse_go_test(self, output: str, exit_code: int) -> ParsedResult:
        """Parse Go test output."""
        result = ParsedResult(
            framework=TestFramework.GO_TEST,
            raw_output=output,
        )

        # Count PASS and FAIL
        result.passed_tests = len(re.findall(r"--- PASS:", output))
        result.failed_tests = len(re.findall(r"--- FAIL:", output))
        result.total_tests = result.passed_tests + result.failed_tests

        # Parse failures
        failure_pattern = re.compile(
            r"--- FAIL:\s+(\w+)\s+\([\d.]+s\)\n(.*?)(?=--- |ok\s|\Z)",
            re.DOTALL,
        )
        for match in failure_pattern.finditer(output):
            result.test_results.append(
                TestResult(
                    name=match.group(1),
                    passed=False,
                    error_message=match.group(2).strip(),
                )
            )

        return result

    def _parse_cargo_test(self, output: str, exit_code: int) -> ParsedResult:
        """Parse Cargo test output."""
        result = ParsedResult(
            framework=TestFramework.CARGO_TEST,
            raw_output=output,
        )

        # Parse summary: "test result: ok. 5 passed; 0 failed"
        summary_match = re.search(
            r"test result:.*?(\d+) passed;\s*(\d+) failed",
            output,
        )
        if summary_match:
            result.passed_tests = int(summary_match.group(1))
            result.failed_tests = int(summary_match.group(2))
            result.total_tests = result.passed_tests + result.failed_tests

        # Parse failures
        failure_pattern = re.compile(
            r"---- (\w+) stdout ----\n(.*?)(?=----|\Z)",
            re.DOTALL,
        )
        for match in failure_pattern.finditer(output):
            if "FAILED" in output:
                result.test_results.append(
                    TestResult(
                        name=match.group(1),
                        passed=False,
                        error_message=match.group(2).strip(),
                    )
                )

        return result

    def _parse_generic(self, output: str, exit_code: int) -> ParsedResult:
        """Parse generic command output based on exit code."""
        result = ParsedResult(
            framework=TestFramework.UNKNOWN,
            raw_output=output,
        )

        # For generic commands, we only have exit code to go on
        if exit_code == 0:
            result.total_tests = 1
            result.passed_tests = 1
        else:
            result.total_tests = 1
            result.failed_tests = 1
            result.test_results.append(
                TestResult(
                    name="command",
                    passed=False,
                    error_message=output[:500] if output else "Command failed",
                )
            )

        return result

    def extract_error_locations(self, output: str) -> list[dict]:
        """Extract file locations mentioned in error output.

        Args:
            output: Error output text

        Returns:
            List of dicts with file, line, message
        """
        locations = []

        # Python tracebacks: File "path", line N
        python_pattern = re.compile(
            r'File "([^"]+)", line (\d+).*?\n\s*(.+)',
            re.MULTILINE,
        )
        for match in python_pattern.finditer(output):
            locations.append(
                {
                    "file": match.group(1),
                    "line": int(match.group(2)),
                    "message": match.group(3).strip(),
                }
            )

        # JavaScript: at path:line:col
        js_pattern = re.compile(
            r"at\s+(?:\w+\s+)?\(?([^:]+):(\d+)(?::\d+)?\)?",
            re.MULTILINE,
        )
        for match in js_pattern.finditer(output):
            locations.append(
                {
                    "file": match.group(1),
                    "line": int(match.group(2)),
                    "message": "",
                }
            )

        # Go: path:line:col: message
        go_pattern = re.compile(
            r"([^\s:]+\.go):(\d+)(?::\d+)?:\s*(.+)",
            re.MULTILINE,
        )
        for match in go_pattern.finditer(output):
            locations.append(
                {
                    "file": match.group(1),
                    "line": int(match.group(2)),
                    "message": match.group(3).strip(),
                }
            )

        return locations
