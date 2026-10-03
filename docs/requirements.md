# Project Requirements

## A. OFFICIAL MANDATORY REQUIREMENTS
1. Accept one Job Description (PDF).
2. Accept a batch of 15–18 resumes (PDF).
3. Evaluate every resume against the JD.
4. Genuinely use BOTH semantic matching and keyword matching.
5. Both matching methods must contribute to the final ranking result.
6. Produce a ranked list of all candidates from best fit to worst fit.
7. Produce a final score for every candidate.
8. For the top 3 candidates, provide explainability:
   - Why they ranked there.
   - Which skills matched.
   - Which required skills appear to be missing.

## B. OFFICIAL BONUS REQUIREMENTS
1. Detect potential bias or overly narrow phrasing in the JD.
2. Provide a recruiter chat/natural-language interface (e.g., "Why is Candidate X ranked above Y?").
3. Handle messy/inconsistent resume formatting gracefully (typos, varied dates, inconsistent headers).

## C. PROJECT-LEVEL CONSTRAINTS
- **Local Only:** The complete system must operate locally.
- **No External APIs:** No OpenAI API, Gemini API, Claude API, cloud LLM APIs, cloud embedding APIs, cloud vector databases, or any service requiring internet.
- **No Fake Ranking:** Do not use an LLM API simply to generate a fake "out of 100" score. Genuine algorithmic implementation is required.
- **No Fabricated Final Data:** Do not use fabricated JDs or resumes for the final evaluation (organizer data will be used). Independent test fixtures must be used for unit testing.

## D. PROPOSED INNOVATION FEATURES
(To be implemented in future phases based on research gaps, e.g., contextual section-bound verification or real-time weight tuning).
