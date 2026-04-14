# Topic Classification Rules

The agent uses this map to assign a topic and subtopic to every reel.
When an existing topic fits, reuse it exactly (spelling matters — Notion is case-sensitive).
When nothing fits, create a new topic/subtopic following the same naming style.

---

## Technology
- AI & Machine Learning
- Software Engineering
- Web Development
- Cybersecurity
- Hardware & Gadgets
- Productivity Tools

## Business & Finance
- Entrepreneurship
- Investing & Markets
- Personal Finance
- Marketing & Growth
- Leadership & Management

## Science
- Physics & Space
- Biology & Health
- Chemistry & Environment
- Mathematics

## Personal Development
- Mindset & Psychology
- Habits & Routines
- Communication Skills
- Time Management

## Health & Fitness
- Nutrition & Diet
- Exercise & Training
- Mental Health
- Sleep & Recovery

## Arts & Culture
- Music & Audio
- Film & Video
- Design & Visual Arts
- Writing & Storytelling

## Cooking & Food
- Recipes & Techniques
- Nutrition Facts
- Food Science

## Travel & Geography
- Destinations
- Culture & History
- Travel Tips

---

## Classification Rules

1. **Prefer specificity** — "AI & Machine Learning" over "Technology" when the content is clearly about AI.
2. **Reuse existing topics** — call `get_existing_topics` first; match before creating new ones.
3. **One topic, one subtopic** — do not assign multiple categories to a single reel.
4. **Short subtopics** — keep subtopic labels under 30 characters.
5. **Unknown content** — if the transcript is too short or unclear, use topic "Uncategorised" / subtopic "Review Needed".
