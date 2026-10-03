from typing import List, Dict, Any, Optional
from app.schemas.career_twin import CareerTwin
from app.schemas.domain import JobDescription
from app.schemas.coach_api import JobFitAnalysisResponse

class InterviewCoachService:
    """
    Adapter and orchestration service for interview preparation.
    Generates targeted technical and behavioral questions grounded in resume gaps and project claims.
    """

    def generate_interview_prep(self, twin: CareerTwin, fit_response: Optional[JobFitAnalysisResponse] = None) -> Dict[str, Any]:
        """
        Generates structured interview preparation items based on CareerTwin and JobFit gaps.
        """
        questions: List[Dict[str, Any]] = []

        # 1. Project Deep-Dive Questions (Verifying authentic engineering decisions)
        for proj in twin.projects[:3]:
            questions.append({
                "category": "Project Architecture & Deep Dive",
                "target_claim": proj.name,
                "question": f"In your project '{proj.name}', what were the most significant technical trade-offs you encountered when choosing {'/'.join(proj.technologies[:2]) if proj.technologies else 'your architecture'}?",
                "focus_area": "Technical depth and ownership",
            })

        # 2. Experience Deep-Dive Questions
        if twin.experience:
            top_exp = twin.experience[0]
            questions.append({
                "category": "Behavioral & STAR Scenario",
                "target_claim": f"{top_exp.role} at {top_exp.company}",
                "question": f"Describe a high-stakes challenge or production issue you resolved as {top_exp.role} at {top_exp.company}. Break down your answer using Situation, Task, Action, and Result.",
                "focus_area": "STAR storytelling and measurable impact",
            })

        # 3. Gap-Probing Questions (from JobFit analysis if provided)
        if fit_response and fit_response.critical_gaps:
            for gap in fit_response.critical_gaps[:3]:
                questions.append({
                    "category": "Qualification & Gap Probing",
                    "target_claim": gap,
                    "question": f"The position strongly emphasizes {gap.replace('Missing required qualification: ', '')}. While this isn't prominent in your recent work, how have your existing skills prepared you to ramp up rapidly on this?",
                    "focus_area": "Learning agility and transferable skills",
                })

        return {
            "total_questions_generated": len(questions),
            "questions": questions,
            "star_framework_guide": {
                "S": "Situation: Set the scene and explain the business or technical context.",
                "T": "Task: Clarify your explicit responsibility in the scenario.",
                "A": "Action: Describe the precise technical tools and strategies YOU implemented.",
                "R": "Result: Quantify the outcome (performance boost, team efficiency, metric gains)."
            }
        }

    def evaluate_star_answer(self, user_answer: str) -> Dict[str, Any]:
        """
        Baseline rule-based STAR completeness analysis.
        """
        lower = user_answer.lower()
        has_situation = any(k in lower for k in ["when", "during", "at my", "project", "problem", "challenge", "company"])
        has_task = any(k in lower for k in ["responsible", "goal", "task", "needed to", "my role", "objective"])
        has_action = any(k in lower for k in ["implemented", "built", "designed", "used", "created", "refactored", "wrote", "decided"])
        has_result = any(k in lower for k in ["result", "reduced", "increased", "improved", "percent", "%", "achieved", "delivered"])

        score = sum([has_situation, has_task, has_action, has_result]) * 25

        missing = []
        if not has_situation:
            missing.append("Situation (context/background)")
        if not has_task:
            missing.append("Task (your explicit objective)")
        if not has_action:
            missing.append("Action (concrete technical steps taken)")
        if not has_result:
            missing.append("Result (quantified outcome or metric improvement)")

        return {
            "star_score": score,
            "components_present": {
                "situation": has_situation,
                "task": has_task,
                "action": has_action,
                "result": has_result,
            },
            "missing_components": missing,
            "coaching_tip": "Always conclude your answer with measurable results (e.g. latency reduced by 30%, user satisfaction up)." if not has_result else "Great articulation of outcomes!"
        }
