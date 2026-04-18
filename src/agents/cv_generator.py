"""CVGeneratorAgent - generates tailored CV content."""

from typing import Any

from src.agents.base import BaseAgent
from src.models import (
    ConfigOutput,
    MaterialsOutput,
    JobAnalysisOutput,
    CVContentOutput,
)


CV_GENERATOR_PROMPT = """You are an expert CV writer who creates tailored, professional resumes that highlight relevant experience for specific job opportunities.

Generate a professional CV tailored to the target job. Your CV should:

1. **Match the Job**: Prioritize experience and skills that align with job requirements
2. **Be Concise**: Use action verbs, quantify achievements, avoid fluff
3. **Be Honest**: Only include information from the provided materials
4. **Be Professional**: Follow industry standards for the specified style

## Content Guidelines

### Summary Section
- 2-3 sentences maximum
- Highlight most relevant experience for the target role
- Include years of experience and key strength areas
- Mention 1-2 achievements if space allows

### Experience Section
- Reverse chronological order (unless functional template)
- Use action verbs: Led, Built, Delivered, Achieved, Reduced, Increased
- Quantify achievements: percentages, dollar amounts, team sizes
- Focus on results, not just responsibilities
- 3-5 bullet points per role for recent positions

### Skills Section
- Group by category (Technical, Leadership, etc.)
- Prioritize skills mentioned in job requirements
- Be specific (Python, not "programming languages")

### Education Section
- Include degree, institution, year
- Add relevant details only if recent graduate or prestigious

## Style Guidelines

### Modern Style (default)
- Clean, direct language with action verbs
- First person implied (no "I")
- Bullet points with measurable achievements
- Short, punchy sentences
- Example: "Led 12-person team to 25% efficiency gain through process automation"

### Formal Style
- Traditional, conservative language
- Full sentences, no contractions
- Third person or passive voice preferred
- Example: "Managed a team of 12 professionals, achieving a 25% increase in efficiency."

### Technical Style
- Emphasis on technical skills, tools, methodologies
- Detailed specifications and metrics
- Include version numbers, stack details
- Example: "Architected microservices migration (K8s, Go, gRPC) for 12-engineer team; reduced deployment time 25%"

### Creative Style
- Personality-driven, storytelling elements
- Shows creativity through word choice
- Example: "Transformed a struggling team of 12 into efficiency champions, slashing waste by 25%"

## Output Format

Return a JSON object with this structure:

```json
{
  "name": "Full Name",
  "contact": {
    "email": "email@example.com",
    "phone": "+1234567890",
    "linkedin": "linkedin.com/in/name",
    "github": "github.com/name",
    "website": null,
    "address": null
  },
  "summary": "2-3 sentence summary...",
  "experience": [
    {
      "title": "Job Title",
      "company": "Company Name",
      "location": "City, Country",
      "start_date": "Jan 2020",
      "end_date": null,
      "achievements": [
        "Achievement 1 with metrics",
        "Achievement 2 with impact"
      ]
    }
  ],
  "education": [
    {
      "degree": "MSc Computer Science",
      "institution": "University Name",
      "year": "2019",
      "details": "Relevant coursework or honors"
    }
  ],
  "skills": {
    "categories": {
      "Technical": ["Python", "AWS", "Docker"],
      "Leadership": ["Team management", "Strategy"]
    }
  },
  "awards": ["Award 1", "Award 2"],
  "additional": ["Language: Spanish (native)", "Publications: ..."],
  "estimated_pages": 2
}
```

## Important Notes

- Never invent information not in the source materials
- Keep within page limit by prioritizing recent/relevant experience
- Match keywords from job description where honest
- Use the language specified in configuration
- For 1-page CVs: Only most recent 2-3 roles, brief bullets
- For 2-page CVs: Full recent history, detailed achievements
- For 3-page CVs: Extended history, publications, projects
"""


class CVGeneratorAgent(BaseAgent):
    """Agent that generates tailored CV content."""

    agent_name = "cv_generator"

    @property
    def requires_llm(self) -> bool:
        return True

    async def run(
        self,
        config: ConfigOutput,
        materials: MaterialsOutput,
        job_analysis: JobAnalysisOutput,
    ) -> CVContentOutput:
        """Generate tailored CV content.

        Args:
            config: Configuration with style, language, etc.
            materials: User's background materials.
            job_analysis: Analyzed job requirements.

        Returns:
            Generated CV content.
        """
        # Build comprehensive prompt
        user_content = self._build_user_prompt(config, materials, job_analysis)

        messages = self.build_messages(user_content, system_content=CV_GENERATOR_PROMPT)
        response = await self.llm_client.complete(messages, max_tokens=8192)

        result = await self.parse_json_response(response, CVContentOutput)

        # Add metadata
        result.style_applied = config.style
        result.template_applied = config.template
        result.language = config.language

        return result

    def _build_user_prompt(
        self,
        config: ConfigOutput,
        materials: MaterialsOutput,
        job_analysis: JobAnalysisOutput,
    ) -> str:
        """Build the user prompt with all context.

        Args:
            config: Configuration.
            materials: User materials.
            job_analysis: Job analysis.

        Returns:
            Formatted prompt string.
        """
        # Aggregate materials
        if materials.documents:
            materials_text = "\n\n---\n\n".join(
                f"## {doc.file_name}\n{doc.content}"
                for doc in materials.documents
            )
        else:
            materials_text = "(No materials provided)"

        # Format required skills
        required_skills = "\n".join(
            f"- {s}" for s in job_analysis.required_skills
        ) or "- Not specified"

        # Format nice-to-have skills
        nice_to_have = "\n".join(
            f"- {s}" for s in job_analysis.nice_to_have_skills
        ) or "- None specified"

        # Format responsibilities
        responsibilities = "\n".join(
            f"- {r}" for r in job_analysis.responsibilities
        ) or "- Not specified"

        # Format contact info to include
        contact_info = ", ".join(config.contact_info)

        prompt = f"""Generate a tailored CV for the following job:

## Target Job
- **Title:** {job_analysis.job_title}
- **Company:** {job_analysis.company_name or "Not specified"}
- **Location:** {job_analysis.location or "Not specified"}
- **Industry:** {job_analysis.industry or "Not specified"}

### Required Skills
{required_skills}

### Nice-to-Have Skills
{nice_to_have}

### Key Responsibilities
{responsibilities}

---

## User's Background Materials

{materials_text}

---

## CV Configuration

- **Language:** {config.language}
- **Max Pages:** {config.max_pages}
- **Style:** {config.style}
- **Template:** {config.template}
- **Contact Info to Include:** {contact_info}
"""

        if config.other_instructions:
            prompt += f"""
## Additional Instructions
{config.other_instructions}
"""

        prompt += f"""
---

Generate a CV that:
1. Highlights experience and skills matching the job requirements
2. Uses the **{config.style}** style
3. Follows the **{config.template}** template structure
4. Fits within **{config.max_pages}** page(s)
5. Is written in **{config.language}**

Return the CV content as structured JSON."""

        return prompt
