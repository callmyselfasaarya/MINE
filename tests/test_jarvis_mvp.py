import unittest
from jarvis.core.agent import jarvis_agent
from jarvis.tools.registry import registry

class TestMineMVP(unittest.TestCase):

    def setUp(self):
        jarvis_agent.conversation.clear()
        if jarvis_agent.guardrails.has_pending_action():
            jarvis_agent.guardrails.cancel()

    def test_01_user_prompt_scenario(self):
        """Test exact prompt scenario: 'Mine, remind me tomorrow at 8 AM to submit my project.'"""
        res = jarvis_agent.interact("Mine, remind me tomorrow at 8 AM to submit my project.", speak_output=False)
        self.assertEqual(res.get("tool_called"), "create_reminder")
        self.assertTrue("submit project" in res.get("text").lower() or "submit my project" in res.get("text").lower())
        self.assertIn("08:00 AM", res.get("text"))

    def test_02_memory_system(self):
        """Test remembering user facts and recalling them."""
        res1 = jarvis_agent.interact("Remember that my coffee preference is black coffee.", speak_output=False)
        self.assertEqual(res1.get("tool_called"), "remember_fact")

        res2 = jarvis_agent.interact("What do you remember about my coffee preference?", speak_output=False)
        self.assertEqual(res2.get("tool_called"), "recall_facts")

    def test_03_calendar_management(self):
        """Test scheduling calendar events."""
        res = jarvis_agent.interact("Schedule quarterly project review on 2026-10-05 at 14:00", speak_output=False)
        self.assertEqual(res.get("tool_called"), "create_calendar_event")
        self.assertIn("quarterly project review", res.get("text").lower())

    def test_04_document_management(self):
        """Test document creation and reading."""
        res1 = jarvis_agent.interact("Create document sprint_goals.txt with content Launch MINE MVP today", speak_output=False)
        self.assertEqual(res1.get("tool_called"), "create_document")

        res2 = jarvis_agent.interact("Read file sprint_goals.txt", speak_output=False)
        self.assertEqual(res2.get("tool_called"), "read_file")
        self.assertIn("Launch MINE MVP today", str(res2.get("tool_result")))

    def test_05_system_vitals(self):
        """Test computer telemetry."""
        res = jarvis_agent.interact("What is my computer system status?", speak_output=False)
        self.assertEqual(res.get("tool_called"), "get_system_status")
        self.assertIn("CPU", res.get("text"))

    def test_06_search_web(self):
        """Test web search query."""
        res = jarvis_agent.interact("Search the web for python asyncio tutorial", speak_output=False)
        self.assertEqual(res.get("tool_called"), "search_web")

    def test_07_dangerous_action_confirmation_lifecycle(self):
        """Test guardrails: confirmation prompt -> abort -> re-prompt -> authorize."""
        # 1. Trigger dangerous action
        res1 = jarvis_agent.interact("Delete the file sprint_goals.txt", speak_output=False)
        self.assertTrue(res1.get("requires_confirmation"))
        self.assertEqual(res1.get("status"), "requires_confirmation")
        self.assertTrue(jarvis_agent.guardrails.has_pending_action())

        # 2. Reject it
        res2 = jarvis_agent.interact("No, cancel that action.", speak_output=False)
        self.assertEqual(res2.get("status"), "cancelled")
        self.assertFalse(jarvis_agent.guardrails.has_pending_action())

        # 3. Trigger again and authorize
        res3 = jarvis_agent.interact("Delete the file sprint_goals.txt", speak_output=False)
        self.assertTrue(res3.get("requires_confirmation"))
        
        res4 = jarvis_agent.interact("Yes, proceed and authorize.", speak_output=False)
        self.assertEqual(res4.get("status"), "confirmed")
        self.assertFalse(jarvis_agent.guardrails.has_pending_action())


if __name__ == "__main__":
    unittest.main()