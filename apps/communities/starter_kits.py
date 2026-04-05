from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class StarterKit:
    key: str
    label: str
    tagline: str
    description: str
    defaults: dict
    rules: list[tuple[str, str]] = field(default_factory=list)
    flairs: list[str] = field(default_factory=list)
    wiki_title: str = "Welcome"
    wiki_body: str = ""
    challenge_title: str = ""
    challenge_prompt: str = ""


STARTER_KITS: tuple[StarterKit, ...] = (
    StarterKit(
        key="discussion_club",
        label="Discussion club",
        tagline="For thoughtful conversation and regular prompts.",
        description="A calm room for recurring prompts, reflection, and long-form discussion.",
        defaults={
            "community_type": "public",
            "allow_text_posts": True,
            "allow_link_posts": True,
            "allow_image_posts": False,
            "allow_polls": True,
            "landing_intro_md": "A home for generous conversation, recurring prompts, and thoughtful replies.",
            "faq_md": "## Start here\n\n- Introduce yourself\n- Link to discussions worth reading\n- Vote for the prompts you want next",
            "best_of_md": "- Weekly reflection thread\n- Reading round-up\n- Best newcomer intros",
            "seo_description": "A discussion-first community for thoughtful prompts and recurring conversations.",
            "sidebar_md": "## What belongs here\n\nShare a prompt, reflect on someone else's idea, and keep replies generous.",
        },
        rules=[
            ("Prefer reflection over outrage", "Take a beat before posting and help the thread stay useful."),
            ("Add context", "If you share a link, tell people why it matters."),
        ],
        flairs=["Prompt", "Reflection", "Question"],
        wiki_title="How this club works",
        wiki_body="## Discussion rhythm\n\n1. Start with a clear prompt.\n2. Reply to someone new.\n3. Bring links with context, not as drive-by posts.",
        challenge_title="Opening prompt week",
        challenge_prompt="Write one prompt that helps strangers get to know your perspective in a generous way.",
    ),
    StarterKit(
        key="design_critique",
        label="Design critique",
        tagline="For makers who want screenshots, drafts, and useful feedback.",
        description="A studio-like setup for sharing work in progress and getting actionable critique.",
        defaults={
            "community_type": "public",
            "allow_text_posts": True,
            "allow_link_posts": True,
            "allow_image_posts": True,
            "allow_polls": False,
            "landing_intro_md": "A critique room for interface ideas, prototypes, and product design tradeoffs.",
            "faq_md": "## Posting tips\n\n- Tell people what feedback you want\n- Share constraints\n- Follow up with what changed",
            "best_of_md": "- Best redesign breakdowns\n- Useful critique prompts\n- Before/after threads",
            "seo_description": "A design critique community for UI feedback, prototypes, and thoughtful iteration.",
            "sidebar_md": "## Feedback culture\n\nShare the goal, the rough edges, and the context before asking for critique.",
        },
        rules=[
            ("Critique the work, not the person", "Keep feedback specific, respectful, and actionable."),
            ("Show your constraint", "Say whether you need feedback on clarity, aesthetics, or usability."),
        ],
        flairs=["WIP", "Feedback", "Case study"],
        wiki_title="How to ask for critique",
        wiki_body="## Better critique requests\n\nMention the audience, the device, and the exact question you want answered.",
        challenge_title="Polish sprint",
        challenge_prompt="Share one screen that feels almost done and invite people to improve a single interaction.",
    ),
    StarterKit(
        key="local_group",
        label="Local group",
        tagline="For place-based communities, events, and neighborhood coordination.",
        description="A practical layout for local clubs, meetups, and place-driven sharing.",
        defaults={
            "community_type": "restricted",
            "allow_text_posts": True,
            "allow_link_posts": True,
            "allow_image_posts": True,
            "allow_polls": True,
            "landing_intro_md": "A local room to coordinate events, recommendations, and small community updates.",
            "faq_md": "## Keep it local\n\n- Share a place or event\n- Help new people orient themselves\n- Keep personal info off-thread",
            "best_of_md": "- Monthly meetup thread\n- Favorite local spots\n- Trusted resources",
            "seo_description": "A local community hub for events, recommendations, and neighborhood coordination.",
            "sidebar_md": "## Local first\n\nUse this space for nearby events, practical help, and community updates.",
        },
        rules=[
            ("Protect privacy", "Do not post someone else's personal details."),
            ("Add the basics", "Dates, places, and context make local threads more useful."),
        ],
        flairs=["Event", "Recommendation", "Need help"],
        wiki_title="Local guide",
        wiki_body="## Community basics\n\nPin recurring meetups, local resources, and how new members can introduce themselves.",
        challenge_title="Neighborhood intro week",
        challenge_prompt="Post one favorite local place and tell people why it matters to you.",
    ),
    StarterKit(
        key="challenge_room",
        label="Prompt / challenge room",
        tagline="For weekly prompts, sprints, and themed participation.",
        description="A community optimized for recurring themed participation and lightweight competition.",
        defaults={
            "community_type": "public",
            "allow_text_posts": True,
            "allow_link_posts": False,
            "allow_image_posts": True,
            "allow_polls": True,
            "landing_intro_md": "A fast-moving room built around recurring prompts, challenges, and playful accountability.",
            "faq_md": "## How to participate\n\n- Join the current challenge\n- Post your entry\n- Cheer on someone else",
            "best_of_md": "- Hall of fame\n- Prompt archive\n- Best community recaps",
            "seo_description": "A challenge-driven community for recurring prompts, playful competition, and quick participation.",
            "sidebar_md": "## Challenge mode\n\nEach week has a prompt. Post your entry, vote generously, and keep the energy up.",
        },
        rules=[
            ("One entry per prompt", "Keep challenge rounds easy to browse."),
            ("Celebrate effort", "Reward good participation, not just polished output."),
        ],
        flairs=["Entry", "Prompt", "Recap"],
        wiki_title="Prompt archive",
        wiki_body="## Running a challenge room\n\nTrack past prompts, winners, and the best recap threads in one place.",
        challenge_title="Intro week prompt",
        challenge_prompt="Share an intro post that makes strangers want to reply to you.",
    ),
    StarterKit(
        key="slow_blog",
        label="Slow blog / reading group",
        tagline="For essays, reading notes, and curated links with commentary.",
        description="A quieter format for essays, annotated links, and slower discussion rhythms.",
        defaults={
            "community_type": "public",
            "allow_text_posts": True,
            "allow_link_posts": True,
            "allow_image_posts": False,
            "allow_polls": False,
            "landing_intro_md": "A slower room for essays, reading notes, and deeply contextual link sharing.",
            "faq_md": "## Bring context\n\n- Add notes to every link\n- Use excerpts sparingly\n- Follow up with what stayed with you",
            "best_of_md": "- Reading notes\n- Essay club picks\n- Monthly recaps",
            "seo_description": "A reading group style community for essays, notes, and thoughtful link sharing.",
            "sidebar_md": "## Slow by design\n\nShare writing worth spending time with, and say why it matters.",
        },
        rules=[
            ("Explain the link", "Every shared article needs your own framing."),
            ("Choose depth over speed", "Fewer, better threads beat constant churn."),
        ],
        flairs=["Essay", "Reading notes", "Link with context"],
        wiki_title="Reading guide",
        wiki_body="## What makes a good post here\n\nSummarize the piece, quote the key idea, and ask one strong question.",
        challenge_title="Reading notes week",
        challenge_prompt="Share one idea from something you read this week and why it stuck with you.",
    ),
)


STARTER_KIT_MAP = {kit.key: kit for kit in STARTER_KITS}
