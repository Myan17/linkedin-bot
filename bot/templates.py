import os


def initial_message(first_name: str) -> str:
    resume_link = os.getenv("RESUME_LINK", "[RESUME_LINK]")
    github_url = os.getenv("GITHUB_URL", "[GITHUB_URL]")
    school = os.getenv("SCHOOL", "[Your School]")
    role = os.getenv("ROLE", "software engineering")
    year = os.getenv("YEAR", "senior")
    major = os.getenv("MAJOR", "Computer Science")

    return (
        f"Hey {first_name}, hope you're doing well!\n\n"
        f"I'm a {year} studying {major} at {school}, "
        f"actively looking for internship and full-time opportunities in {role}.\n\n"
        f"I'd love to share my resume and GitHub for your reference:\n"
        f"• Resume: {resume_link}\n"
        f"• GitHub: {github_url}\n\n"
        "If anything comes to mind that might be a good fit, I'd genuinely appreciate "
        "any help — even just a pointer in the right direction means a lot.\n\n"
        "Thanks so much for connecting!"
    )


def followup_message(first_name: str) -> str:
    resume_link = os.getenv("RESUME_LINK", "[RESUME_LINK]")

    return (
        f"Hi {first_name}, just wanted to follow up in case my earlier message got buried!\n\n"
        "I'm still exploring opportunities and would love any guidance you might have. "
        f"Resume here if helpful: {resume_link}\n\n"
        "Thanks again for your time — really appreciate it!"
    )
