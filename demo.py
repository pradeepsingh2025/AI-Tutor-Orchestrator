"""
Demo Script for AI Tutor Orchestrator
Tests the orchestrator with various scenarios
"""
import asyncio
import os
from dotenv import load_dotenv
from models import UserInfo, ChatMessage, OrchestrateRequest
from parameter_extractor import ParameterExtractor
from tools import MockToolClient
from orchestrator import AITutorOrchestrator
import json

# Load environment
load_dotenv()


# ============================================================================
# DEMO SCENARIOS
# ============================================================================

DEMO_SCENARIOS = [
    {
        "name": "Scenario 1: Student Needs Practice (Flashcards)",
        "user": {
            "user_id": "student001",
            "name": "Alice",
            "grade_level": "10",
            "learning_style_summary": "Kinesthetic learner, learns best through practice",
            "emotional_state_summary": "Slightly anxious but motivated",
            "mastery_level_summary": "Level 5 - Developing competence"
        },
        "message": "I'm struggling with calculus derivatives and need some practice problems",
        "chat_history": [
            {"role": "user", "content": "Hi, I need help with math"},
            {"role": "assistant", "content": "Of course! What topic are you working on?"}
        ],
        "expected_tool": "flashcard_generator"
    },
    {
        "name": "Scenario 2: Visual Learner Requests Notes",
        "user": {
            "user_id": "student002",
            "name": "Bob",
            "grade_level": "11",
            "learning_style_summary": "Visual learner, prefers diagrams and structured notes",
            "emotional_state_summary": "Focused and ready to learn",
            "mastery_level_summary": "Level 7 - Proficient"
        },
        "message": "Can you help me create notes on photosynthesis for biology?",
        "chat_history": [],
        "expected_tool": "note_maker"
    },
    {
        "name": "Scenario 3: Confused Student Needs Explanation",
        "user": {
            "user_id": "student003",
            "name": "Charlie",
            "grade_level": "9",
            "learning_style_summary": "Auditory learner, prefers simple explanations",
            "emotional_state_summary": "Confused and needs clarification",
            "mastery_level_summary": "Level 3 - Building foundation"
        },
        "message": "I don't understand what mitosis is, can you explain it?",
        "chat_history": [
            {"role": "user", "content": "We're learning about cell division in class"},
            {"role": "assistant", "content": "That's an important topic! What specifically are you having trouble with?"}
        ],
        "expected_tool": "concept_explainer"
    },
    {
        "name": "Scenario 4: High-Achieving Student",
        "user": {
            "user_id": "student004",
            "name": "Diana",
            "grade_level": "12",
            "learning_style_summary": "Advanced learner, enjoys challenges",
            "emotional_state_summary": "Confident and seeking deeper knowledge",
            "mastery_level_summary": "Level 9 - Advanced understanding"
        },
        "message": "I want to dive deep into quantum mechanics, specifically wave-particle duality",
        "chat_history": [],
        "expected_tool": "concept_explainer"
    },
    {
        "name": "Scenario 5: General Conversation (No Tool)",
        "user": {
            "user_id": "student005",
            "name": "Eve",
            "grade_level": "8",
            "learning_style_summary": "Balanced learner",
            "emotional_state_summary": "Friendly and curious",
            "mastery_level_summary": "Level 5 - Developing competence"
        },
        "message": "Hello! How are you doing today?",
        "chat_history": [],
        "expected_tool": "none"
    }
]


# ============================================================================
# DEMO RUNNER
# ============================================================================

class DemoRunner:
    """Runs demo scenarios and displays results"""
    
    def __init__(self):
        """Initialize demo with mock tools"""
        print("🚀 Initializing AI Tutor Orchestrator Demo...")
        print("=" * 70)
        
        # Use mock tools for demo
        self.tool_client = MockToolClient()
        self.parameter_extractor = ParameterExtractor(
            model_name="gpt-4",
            temperature=0.1
        )
        self.orchestrator = AITutorOrchestrator(
            parameter_extractor=self.parameter_extractor,
            tool_client=self.tool_client
        )
        
        print("✅ Demo initialized successfully!\n")
    
    async def run_scenario(self, scenario: dict):
        """Run a single demo scenario"""
        print(f"\n{'='*70}")
        print(f"📚 {scenario['name']}")
        print(f"{'='*70}\n")
        
        # Display student info
        user = scenario['user']
        print(f"👤 Student: {user['name']} (Grade {user['grade_level']})")
        print(f"📖 Learning Style: {user['learning_style_summary']}")
        print(f"😊 Emotional State: {user['emotional_state_summary']}")
        print(f"🎯 Mastery Level: {user['mastery_level_summary']}")
        print(f"\n💬 Student Message: \"{scenario['message']}\"\n")
        
        # Create user info
        user_info = UserInfo(**user)
        
        # Create chat history
        chat_history = [ChatMessage(**msg) for msg in scenario.get('chat_history', [])]
        
        # Run orchestration
        print("⚙️  Processing...")
        try:
            response = await self.orchestrator.orchestrate(
                message=scenario['message'],
                user_info=user_info,
                chat_history=chat_history
            )
            
            # Display results
            print("\n" + "─" * 70)
            print("📊 RESULTS")
            print("─" * 70)
            
            print(f"\n✅ Success: {response.success}")
            print(f"🔧 Tool Used: {response.tool_used}")
            print(f"📋 Expected Tool: {scenario['expected_tool']}")
            
            if response.tool_used == scenario['expected_tool']:
                print("✅ Tool selection CORRECT!")
            else:
                print("⚠️  Tool selection different from expected")
            
            print(f"\n📝 Message to Student:")
            print(f"   {response.message}")
            
            print(f"\n🔍 Extracted Parameters:")
            for key, value in response.extracted_parameters.items():
                if value is not None and key not in ['reasoning', 'missing_parameters']:
                    print(f"   • {key}: {value}")
            
            if response.needs_clarification:
                print(f"\n❓ Clarification Needed:")
                for q in response.clarification_questions:
                    print(f"   • {q}")
            
            # Show sample of tool response
            if response.tool_response and response.success:
                print(f"\n📦 Tool Response Preview:")
                if response.tool_used == "flashcard_generator":
                    flashcards = response.tool_response.get('flashcards', [])
                    print(f"   Generated {len(flashcards)} flashcards")
                    if flashcards:
                        print(f"   Sample: {flashcards[0].get('question', 'N/A')[:60]}...")
                
                elif response.tool_used == "note_maker":
                    sections = response.tool_response.get('note_sections', [])
                    print(f"   Generated {len(sections)} note sections")
                    print(f"   Topic: {response.tool_response.get('topic', 'N/A')}")
                
                elif response.tool_used == "concept_explainer":
                    explanation = response.tool_response.get('explanation', '')
                    print(f"   Explanation length: {len(explanation)} characters")
                    print(f"   Preview: {explanation[:100]}...")
            
            print("\n✅ Scenario completed successfully!")
            
        except Exception as e:
            print(f"\n❌ Error: {str(e)}")
            import traceback
            traceback.print_exc()
    
    async def run_all_scenarios(self):
        """Run all demo scenarios"""
        print("\n🎬 Running All Demo Scenarios")
        print("=" * 70)
        
        for i, scenario in enumerate(DEMO_SCENARIOS, 1):
            await self.run_scenario(scenario)
            
            if i < len(DEMO_SCENARIOS):
                print("\n" + "🔄 Moving to next scenario...\n")
                await asyncio.sleep(1)  # Brief pause between scenarios
        
        print("\n" + "=" * 70)
        print("🎉 All Demo Scenarios Completed!")
        print("=" * 70)
    
    async def run_interactive(self):
        """Run interactive demo where user can input messages"""
        print("\n💬 Interactive Demo Mode")
        print("=" * 70)
        print("Type your messages as a student, or 'quit' to exit\n")
        
        # Default student profile
        user_info = UserInfo(
            user_id="demo_user",
            name="Demo Student",
            grade_level="10",
            learning_style_summary="Balanced learner",
            emotional_state_summary="Engaged and ready to learn",
            mastery_level_summary="Level 5 - Developing competence"
        )
        
        chat_history = []
        
        while True:
            try:
                message = input("\n🎓 You: ").strip()
                
                if message.lower() in ['quit', 'exit', 'q']:
                    print("\n👋 Thanks for trying the demo!")
                    break
                
                if not message:
                    continue
                
                # Add to history
                chat_history.append(ChatMessage(role="user", content=message))
                
                # Orchestrate
                print("\n⚙️  Thinking...")
                response = await self.orchestrator.orchestrate(
                    message=message,
                    user_info=user_info,
                    chat_history=chat_history[-5:]  # Last 5 messages
                )
                
                # Display response
                print(f"\n🤖 AI Tutor: {response.message}")
                print(f"   (Used tool: {response.tool_used})")
                
                # Add to history
                chat_history.append(ChatMessage(role="assistant", content=response.message))
                
            except KeyboardInterrupt:
                print("\n\n👋 Demo interrupted. Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error: {str(e)}")


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

async def main():
    """Main demo entry point"""
    print("\n" + "=" * 70)
    print("🎓 AI TUTOR ORCHESTRATOR - DEMO")
    print("=" * 70)
    print("\nThis demo showcases:")
    print("  • Intelligent parameter extraction from natural language")
    print("  • Automatic tool selection based on student needs")
    print("  • Personalization based on learning style and mastery level")
    print("  • Handling of various student scenarios")
    
    runner = DemoRunner()
    
    # Menu
    print("\n" + "=" * 70)
    print("Choose demo mode:")
    print("  1. Run all pre-defined scenarios (recommended)")
    print("  2. Interactive mode (type your own messages)")
    print("  3. Run single scenario")
    print("=" * 70)
    
    choice = input("\nEnter choice (1-3): ").strip()
    
    if choice == "1":
        await runner.run_all_scenarios()
    
    elif choice == "2":
        await runner.run_interactive()
    
    elif choice == "3":
        print("\nAvailable scenarios:")
        for i, scenario in enumerate(DEMO_SCENARIOS, 1):
            print(f"  {i}. {scenario['name']}")
        
        scenario_num = int(input("\nEnter scenario number: ").strip())
        if 1 <= scenario_num <= len(DEMO_SCENARIOS):
            await runner.run_scenario(DEMO_SCENARIOS[scenario_num - 1])
        else:
            print("Invalid scenario number")
    
    else:
        print("Invalid choice")
    
    # Cleanup
    await runner.tool_client.close()
    print("\n✨ Demo complete!\n")


if __name__ == "__main__":
    asyncio.run(main())