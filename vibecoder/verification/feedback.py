"""Feedback generation from verification failures."""

from dataclasses import dataclass
from typing import Optional

from .parser import OutputParser, ParsedResult
from .runner import CommandResult


@dataclass
class Feedback:
    """Structured feedback from verification failure."""

    summary: str
    details: list[str]
    suggestions: list[str]
    error_locations: list[dict]
    raw_output: str

    def to_text(self) -> str:
        """Convert feedback to text format for AI consumption."""
        lines = [
            "## Verification Failed",
            "",
            f"**Summary:** {self.summary}",
            "",
        ]

        if self.details:
            lines.append("### Details")
            for detail in self.details:
                lines.append(f"- {detail}")
            lines.append("")

        if self.error_locations:
            lines.append("### Error Locations")
            for loc in self.error_locations:
                line_info = f":{loc['line']}" if loc.get("line") else ""
                msg = f" - {loc['message']}" if loc.get("message") else ""
                lines.append(f"- `{loc['file']}{line_info}`{msg}")
            lines.append("")

        if self.suggestions:
            lines.append("### Suggestions")
            for suggestion in self.suggestions:
                lines.append(f"- {suggestion}")
            lines.append("")

        lines.append("### Raw Output")
        lines.append("```")
        # Truncate if too long
        output = self.raw_output
        if len(output) > 3000:
            output = output[:3000] + "\n... (truncated)"
        lines.append(output)
        lines.append("```")

        return "\n".join(lines)


class FeedbackGenerator:
    """Generate actionable feedback from verification failures."""

    def __init__(self) -> None:
        """Initialize the feedback generator."""
        self.parser = OutputParser()

    def generate(
        self,
        results: list[CommandResult],
        task_context: Optional[str] = None,
    ) -> Feedback:
        """Generate feedback from verification results.

        Args:
            results: List of command results
            task_context: Optional context about the task

        Returns:
            Feedback with structured information
        """
        # Collect all failures
        failed_results = [r for r in results if not r.success]

        if not failed_results:
            return Feedback(
                summary="All verification commands passed",
                details=[],
                suggestions=[],
                error_locations=[],
                raw_output="",
            )

        # Parse each failure
        parsed_results = []
        all_output = []
        all_locations = []

        for result in failed_results:
            parsed = self.parser.parse(result.output, result.exit_code)
            parsed_results.append(parsed)
            all_output.append(f"Command: {result.command}\n{result.output}")
            all_locations.extend(
                self.parser.extract_error_locations(result.output)
            )

        # Generate summary
        summary = self._generate_summary(failed_results, parsed_results)

        # Generate details
        details = self._generate_details(failed_results, parsed_results)

        # Generate suggestions
        suggestions = self._generate_suggestions(parsed_results, all_locations)

        return Feedback(
            summary=summary,
            details=details,
            suggestions=suggestions,
            error_locations=all_locations,
            raw_output="\n\n---\n\n".join(all_output),
        )

    def _generate_summary(
        self,
        results: list[CommandResult],
        parsed: list[ParsedResult],
    ) -> str:
        """Generate a summary of failures."""
        total_failed = len(results)
        total_tests_failed = sum(p.failed_tests for p in parsed)

        if total_tests_failed > 0:
            return f"{total_failed} command(s) failed with {total_tests_failed} failing test(s)"
        else:
            return f"{total_failed} verification command(s) failed"

    def _generate_details(
        self,
        results: list[CommandResult],
        parsed: list[ParsedResult],
    ) -> list[str]:
        """Generate detailed failure information."""
        details = []

        for result, parsed_result in zip(results, parsed):
            if result.timed_out:
                details.append(f"`{result.command}` timed out")
            elif parsed_result.test_results:
                for test in parsed_result.test_results:
                    if not test.passed:
                        detail = f"Test `{test.name}` failed"
                        if test.error_message:
                            # Truncate long error messages
                            msg = test.error_message[:200]
                            if len(test.error_message) > 200:
                                msg += "..."
                            detail += f": {msg}"
                        details.append(detail)
            else:
                details.append(
                    f"`{result.command}` exited with code {result.exit_code}"
                )

        return details

    def _generate_suggestions(
        self,
        parsed: list[ParsedResult],
        locations: list[dict],
    ) -> list[str]:
        """Generate suggestions for fixing issues."""
        suggestions = []

        # Check for common patterns
        all_output = " ".join(p.raw_output for p in parsed).lower()

        # Import errors
        if "import" in all_output and "error" in all_output:
            suggestions.append(
                "Check for missing imports or incorrect module paths"
            )

        # Syntax errors
        if "syntax" in all_output:
            suggestions.append(
                "Fix syntax errors - check for missing brackets, quotes, or semicolons"
            )

        # Type errors
        if "type" in all_output and "error" in all_output:
            suggestions.append(
                "Review type annotations and ensure correct types are used"
            )

        # Undefined/not found
        if "undefined" in all_output or "not found" in all_output or "not defined" in all_output:
            suggestions.append(
                "Check for undefined variables or missing function/method definitions"
            )

        # Assertion errors
        if "assert" in all_output:
            suggestions.append(
                "Review assertion failures - check expected vs actual values"
            )

        # Connection/network errors
        if "connection" in all_output or "network" in all_output:
            suggestions.append(
                "Check network configuration and ensure services are running"
            )

        # Permission errors
        if "permission" in all_output or "access denied" in all_output:
            suggestions.append(
                "Check file permissions and ensure proper access rights"
            )

        # File specific suggestions based on locations
        if locations:
            files = set(loc["file"] for loc in locations if loc.get("file"))
            if files:
                suggestions.append(
                    f"Focus on these files: {', '.join(list(files)[:5])}"
                )

        # Default suggestion
        if not suggestions:
            suggestions.append(
                "Review the error output carefully and address each issue"
            )

        return suggestions

    def generate_ai_prompt(
        self,
        feedback: Feedback,
        iteration: int,
        max_iterations: int,
    ) -> str:
        """Generate a prompt for the AI to fix issues.

        Args:
            feedback: The generated feedback
            iteration: Current iteration number
            max_iterations: Maximum iterations allowed

        Returns:
            Prompt text for the AI
        """
        remaining = max_iterations - iteration
        urgency = ""
        if remaining <= 2:
            urgency = f"\n\n**IMPORTANT:** Only {remaining} iteration(s) remaining. Focus on the most critical issues."

        return f"""The previous implementation failed verification. Please fix the issues.

{feedback.to_text()}
{urgency}

Please:
1. Analyze each error carefully
2. Make the necessary fixes
3. Ensure your changes will make the verification pass
"""
