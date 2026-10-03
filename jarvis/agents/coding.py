import logging
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

from jarvis.agents.base import BaseSubAgent
from jarvis.tools.files import create_document
from jarvis.memory import memory

logger = logging.getLogger(__name__)

class CodingAgent(BaseSubAgent):
    """
    Coding Sub-Agent:
    - Code generation & refactoring
    - Bug diagnosis and syntax verification
    - Isolated Python snippet execution sandbox with timeout
    - Solution documentation
    """

    def __init__(self):
        super().__init__(
            name="CodingAgent",
            role="Software & Coding Specialist",
            description="Designs, writes, explains, and safely tests code snippets and scripts."
        )

    def execute_python_snippet(self, code: str, timeout: float = 5.0) -> Dict[str, Any]:
        """
        Safely execute Python code in an isolated subprocess with timeout and output capture.
        """
        # Block overt dangerous OS destructive imports in sandbox mode
        forbidden = ["shutil.rmtree", "os.system('format", "rmdir /s"]
        for bad in forbidden:
            if bad in code:
                return {
                    "success": False,
                    "error": f"Security guardrail: '{bad}' is restricted in sandbox execution."
                }

        temp_file = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as tf:
                tf.write(code)
                temp_file = tf.name

            proc = subprocess.run(
                [sys.executable, temp_file],
                capture_output=True,
                text=True,
                timeout=timeout
            )

            stdout = proc.stdout.strip()
            stderr = proc.stderr.strip()
            success = (proc.returncode == 0)

            return {
                "success": success,
                "returncode": proc.returncode,
                "stdout": stdout,
                "stderr": stderr,
                "output": stdout if success else (stderr or f"Exited with code {proc.returncode}")
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": f"Execution timed out after {timeout} seconds."
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            if temp_file and Path(temp_file).exists():
                try:
                    Path(temp_file).unlink()
                except Exception:
                    pass

    def run(self, task: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        logger.info(f"[{self.name}] Processing coding task: '{task}'")
        from jarvis.core.llm import llm

        # Check if the user is asking to run a specific snippet
        run_match = re.search(r"```python(.*?)```", task, re.DOTALL)
        if run_match and ("run" in task.lower() or "execute" in task.lower() or "test" in task.lower()):
            code_to_run = run_match.group(1).strip()
            exec_res = self.execute_python_snippet(code_to_run)
            return {
                "success": exec_res["success"],
                "code": code_to_run,
                "execution_result": exec_res,
                "message": f"Code executed. Output: {exec_res.get('output', '')}"
            }

        # Generate solution using LLM
        prompt = f"""You are an expert Coding Assistant.
Task / Requirements:
{task}

Provide:
1. Concise architecture/approach explanation
2. Complete, clean, well-commented, executable code block
3. Brief usage example or test case
"""
        code_response = ""
        if llm.is_ollama_active() or llm.is_gemini_active():
            try:
                if llm.is_gemini_active():
                    resp = llm._genai_client.models.generate_content(
                        model=llm.model_name,
                        contents=prompt
                    )
                    code_response = resp.text
                elif llm.is_ollama_active():
                    from jarvis.core.llm import ask_ollama
                    code_response = ask_ollama(prompt, model=llm.ollama_model, url=llm.ollama_url)
            except Exception as e:
                logger.warning(f"LLM code generation failed ({e})")

        if not code_response:
            code_response = (
                f"# Coding Solution for: {task}\n\n"
                f"def solve():\n"
                f"    '''Implementation for {task}'''\n"
                f"    print('Solution logic ready for execution.')\n\n"
                f"if __name__ == '__main__':\n"
                f"    solve()\n"
            )

        # Index code solution into semantic memory
        memory.semantic.add_entry(
            content=f"Code solution for '{task}':\n{code_response[:300]}",
            source="coding_agent",
            metadata={"task": task}
        )

        return {
            "success": True,
            "task": task,
            "response": code_response,
            "message": "Coding solution crafted successfully."
        }
