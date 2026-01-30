"""System prompts and templates for VibeCoder."""


class SystemPrompts:
    """Collection of system prompts for different contexts."""

    CODING_AGENT = """You are an expert software engineer working on a coding task. Your goal is to implement the requirements exactly as specified and ensure all verification commands pass.

## Guidelines

1. **Follow Requirements Exactly**: Implement each requirement as specified. Don't add features that weren't requested.

2. **File Operations**: When you need to create or modify files, use the provided tools:
   - Use `write_file` to create or overwrite files
   - Use `read_file` to read existing files
   - Always provide complete file contents, not partial updates

3. **Code Quality**:
   - Write clean, readable code with appropriate comments
   - Follow the existing code style if modifying an existing project
   - Handle errors appropriately
   - Include necessary imports

4. **Verification**: The verification commands will be run after your changes. Make sure your implementation will pass them.

5. **Iteration**: If verification fails, you'll receive feedback about what went wrong. Use this to fix issues in the next iteration.

6. **Completion**: When you believe all requirements are met and verification should pass, clearly indicate this in your response.

## Response Format

Structure your response as follows:

1. **Analysis**: Briefly explain your understanding of what needs to be done
2. **Implementation**: Describe the changes you're making
3. **File Operations**: Use the tools to create/modify files
4. **Verification Notes**: Explain how your changes satisfy the verification commands

Remember: Your changes will be automatically verified. Focus on making the verification commands pass."""

    FEEDBACK_ANALYSIS = """Analyze the following verification output and provide specific, actionable feedback for fixing the issues.

## Verification Output
{verification_output}

## Instructions

1. Identify the specific errors or failures
2. Explain the root cause of each issue
3. Provide concrete suggestions for fixing each issue
4. Prioritize the most critical issues first

Format your response as a clear, numbered list of issues and fixes."""

    @classmethod
    def get_coding_prompt(
        cls,
        task_context: str,
        previous_feedback: str | None = None,
    ) -> str:
        """Generate the full system prompt for a coding task.

        Args:
            task_context: The task description and requirements
            previous_feedback: Feedback from the previous iteration, if any

        Returns:
            The complete system prompt
        """
        prompt = cls.CODING_AGENT + "\n\n## Current Task\n\n" + task_context

        if previous_feedback:
            prompt += f"\n\n## Feedback from Previous Iteration\n\n{previous_feedback}"
            prompt += "\n\nPlease address the issues identified in the feedback."

        return prompt

    @classmethod
    def get_feedback_prompt(cls, verification_output: str) -> str:
        """Generate a prompt for analyzing verification failures.

        Args:
            verification_output: The output from verification commands

        Returns:
            The prompt for feedback analysis
        """
        return cls.FEEDBACK_ANALYSIS.format(verification_output=verification_output)


# Tool definitions for Claude API
TOOL_DEFINITIONS = [
    {
        "name": "write_file",
        "description": "Write content to a file. Creates the file if it doesn't exist, or overwrites if it does.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The file path to write to (relative to working directory)",
                },
                "content": {
                    "type": "string",
                    "description": "The content to write to the file",
                },
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "read_file",
        "description": "Read the contents of a file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The file path to read (relative to working directory)",
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "list_directory",
        "description": "List the contents of a directory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The directory path to list (relative to working directory)",
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "run_command",
        "description": "Run a shell command. Use sparingly and only for tasks that require shell execution.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to run",
                },
            },
            "required": ["command"],
        },
    },
]
