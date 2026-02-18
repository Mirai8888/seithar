"""Seithar Inoculation Engine (SIE).

Generates mechanism-exposure inoculations for each SCT technique.
Based on McGuire's inoculation theory: expose the mechanism, build recognition,
enable autonomous defense.
"""
from seithar.core.taxonomy import SCT_TAXONOMY


_INOCULATIONS = {
    "SCT-001": {
        "mechanism": "Emotional Hijacking bypasses analytical processing by triggering affective responses (fear, outrage, urgency) before the rational mind engages. Content is designed to make you feel before you think.",
        "recognition_signals": [
            "Extreme emotional language disproportionate to the claim",
            "Urgency cues: 'act now', 'before it's too late', 'breaking'",
            "Visceral imagery or language designed to trigger disgust, fear, or anger",
            "Emotional framing of neutral facts"
        ],
        "defense": "When you feel a strong emotional reaction to content, pause. The intensity of your reaction is not correlated with the truth of the claim. Ask: what am I being made to feel, and why would someone want me to feel this way right now?",
        "example": "Headline: 'SHOCKING: They don't want you to see this horrifying truth' -- the emotional loading ('shocking', 'horrifying') is doing the work the evidence should be doing."
    },
    "SCT-002": {
        "mechanism": "Information Asymmetry Exploitation leverages the gap between what the source knows and what the target knows. The attacker controls which information is presented and which is withheld, creating a distorted decision landscape.",
        "recognition_signals": [
            "Claims citing unnamed or unverifiable sources",
            "'Studies show' without identifying which studies",
            "Selective statistics presented without base rates or context",
            "Leaked or classified framing to bypass verification expectations"
        ],
        "defense": "When presented with evidence, ask: what information would I need to verify this claim independently? If that information is systematically unavailable or discouraged, the asymmetry is likely engineered.",
        "example": "'According to insiders...' -- who? What institution? What is their track record? The vagueness is the mechanism."
    },
    "SCT-003": {
        "mechanism": "Authority Fabrication manufactures credibility signals that the source does not legitimately possess. Titles, credentials, institutional affiliations, and expert framing are deployed to short-circuit independent evaluation.",
        "recognition_signals": [
            "Credentials outside the relevant domain ('Dr.' in an unrelated field)",
            "Vague institutional affiliation ('leading researchers')",
            "Appeal to prestige rather than evidence",
            "Fake consensus among manufactured authorities"
        ],
        "defense": "Credentials establish who someone is, not whether they are correct. Evaluate the argument independently of who presents it. Real expertise is verifiable and domain-specific.",
        "example": "'Award-winning scientist reveals...' -- what award? What field? Is the claim within their expertise? The title is doing the work the evidence should do."
    },
    "SCT-004": {
        "mechanism": "Social Proof Manipulation weaponizes conformity instincts by manufacturing the appearance of consensus. Humans use the behavior of others as a decision heuristic. This technique exploits that heuristic with artificial signals.",
        "recognition_signals": [
            "'Everyone knows', 'millions of people agree'",
            "Trending or viral framing to imply validity through popularity",
            "Manufactured engagement (bot networks, coordinated sharing)",
            "Bandwagon language: 'join the movement', 'don't miss out'"
        ],
        "defense": "Popularity is not evidence. The number of people who believe something has no bearing on whether it is true. When you encounter consensus claims, ask: how was this consensus measured, and by whom?",
        "example": "'This post has been shared 100,000 times' -- shares measure virality, not accuracy. The most-shared content is optimized for engagement, not truth."
    },
    "SCT-005": {
        "mechanism": "Identity Targeting calibrates attacks to the target's self-concept and group affiliations. Content is framed so that accepting or rejecting it becomes a statement about who you are rather than what is true.",
        "recognition_signals": [
            "'As a [identity group], you should...'",
            "'Real [group members] know that...'",
            "In-group/out-group framing that ties belief to identity",
            "Content that makes disagreement feel like betrayal of identity"
        ],
        "defense": "Your identity is not an argument. When a claim is framed as something 'people like you' should believe, the identity framing is doing the work the evidence should do. Separate what is being claimed from who is claiming it about whom.",
        "example": "'If you care about [cause], you'll share this' -- caring about something and sharing a specific piece of content are unrelated. The identity bridge is the manipulation."
    },
    "SCT-006": {
        "mechanism": "Temporal Manipulation exploits time pressure, scheduling, and urgency to compress the decision window. Under time pressure, humans default to heuristic processing and are more susceptible to other SCT techniques.",
        "recognition_signals": [
            "Artificial deadlines: 'limited time', 'expires today'",
            "Urgency language disproportionate to the actual stakes",
            "Time-bounded offers or claims that discourage verification",
            "Strategic timing of information release"
        ],
        "defense": "Legitimate urgency is rare. When you feel pressure to act immediately, that pressure is almost always manufactured. The cost of a delayed decision is nearly always lower than the cost of a manipulated one.",
        "example": "'Act before midnight or lose your chance forever' -- real opportunities do not typically expire on arbitrary deadlines designed to prevent comparison shopping."
    },
    "SCT-007": {
        "mechanism": "Recursive Infection creates self-replicating patterns where the target becomes the vector. Content is engineered so that consuming it creates the urge to transmit it, turning each recipient into an amplifier.",
        "recognition_signals": [
            "'Share this before they take it down'",
            "'They don't want you to know this'",
            "Content framed as forbidden or censored to increase sharing impulse",
            "Structures that make not-sharing feel like complicity"
        ],
        "defense": "The urge to share is the mechanism, not a response to truth. Content engineered for virality prioritizes transmissibility over accuracy. When you feel compelled to share something, that compulsion was designed.",
        "example": "'The media won't report this -- spread the word' -- if you are seeing it, the media is not suppressing it. The censorship frame is the transmission mechanism."
    },
    "SCT-008": {
        "mechanism": "Direct Substrate Intervention bypasses information processing entirely by modifying the neural hardware directly through physical or electrical means. This includes historical programs involving surgery, electromagnetic stimulation, or direct brain interfaces.",
        "recognition_signals": [
            "This technique operates below the information layer",
            "Requires physical access to the target",
            "Effects may be attributed to other causes by the target",
            "Historically documented in declassified intelligence programs"
        ],
        "defense": "Awareness of this category exists primarily for completeness. Defense requires physical security and institutional oversight rather than cognitive vigilance.",
        "example": "Documented in MKUltra subprojects involving direct neural intervention. The defense is institutional, not individual."
    },
    "SCT-009": {
        "mechanism": "Chemical Substrate Disruption modifies the neurochemical operating environment through pharmacological means. This alters baseline cognitive function, emotional regulation, and decision-making capacity without the target's awareness or consent.",
        "recognition_signals": [
            "Engineered addictive loops (dopamine manipulation)",
            "Compulsive engagement patterns in digital products",
            "Chemical exposure affecting cognitive baseline",
            "Substances deployed to alter group behavior"
        ],
        "defense": "Recognize that your neurochemical state affects your judgment. Platforms designed for compulsive engagement are exploiting the same substrate. If you cannot stop scrolling, the product is working as designed -- on you.",
        "example": "Infinite scroll, variable-ratio reinforcement in social media feeds, notification patterns designed to trigger dopamine responses. The engagement is the chemical manipulation."
    },
    "SCT-010": {
        "mechanism": "Sensory Channel Manipulation exploits perceptual processing through overload, deprivation, or channel mismatch. The target's ability to process information is degraded by attacking the sensory intake layer.",
        "recognition_signals": [
            "Information flooding beyond processing capacity",
            "Constant notification streams fragmenting attention",
            "Contradictory information from multiple channels simultaneously",
            "Algorithmic amplification of overwhelming content volume"
        ],
        "defense": "Your attention is finite. Systems that demand more attention than you can give are not serving you. Reduce intake channels, batch information consumption, and recognize that feeling overwhelmed is a designed outcome.",
        "example": "Breaking news cycles that produce contradictory updates every 15 minutes. The confusion is not a side effect -- it is the product."
    },
    "SCT-011": {
        "mechanism": "Trust Infrastructure Destruction systematically dismantles the epistemic trust networks that enable collective sensemaking. When no source is trusted, the target defaults to tribal affiliation or paralysis.",
        "recognition_signals": [
            "'Don't trust anyone', 'they're all lying'",
            "Blanket institutional delegitimization",
            "Conspiracy framing that makes all counter-evidence part of the conspiracy",
            "Erosion of trust in measurement and verification itself"
        ],
        "defense": "Total distrust is as exploitable as total trust. The goal of trust destruction is not to make you a better evaluator -- it is to make you unable to evaluate at all. Maintain calibrated trust: verify claims, weight sources by track record, but do not surrender the capacity to trust entirely.",
        "example": "'You can't trust the media, the government, the scientists, or the fact-checkers' -- if nothing is trustworthy, you are left with only tribal allegiance. That is the objective."
    },
    "SCT-012": {
        "mechanism": "Commitment Escalation engineers progressive commitment that becomes self-reinforcing. Small initial agreements are leveraged into larger commitments through sunk-cost exploitation, loyalty testing, and identity binding.",
        "recognition_signals": [
            "'You already agreed to X, so Y follows naturally'",
            "Escalating commitment requests that reference prior agreement",
            "Loyalty tests framed as identity verification",
            "Sunk-cost arguments: 'you've come this far'"
        ],
        "defense": "Past decisions do not obligate future ones. The cost of what you have already invested is irrelevant to whether the next investment is worthwhile. Each decision should be evaluated independently of prior commitments.",
        "example": "'You signed the petition, now attend the rally, now donate, now recruit' -- each step references the prior commitment to make refusal feel like inconsistency. The escalation is the mechanism."
    },
}


def inoculate(sct_code: str) -> dict:
    """Generate a mechanism-exposure inoculation for an SCT technique.
    
    Returns a structured inoculation containing:
    - mechanism: how the technique works
    - recognition_signals: what to look for
    - defense: how to protect yourself
    - example: concrete illustration
    """
    code = sct_code.upper()
    if code not in SCT_TAXONOMY:
        return {"error": f"Unknown technique: {code}"}
    
    tech = SCT_TAXONOMY[code]
    inoc = _INOCULATIONS.get(code)
    
    if not inoc:
        return {
            "code": code,
            "name": tech.name,
            "status": "not_available",
            "message": f"No inoculation template available for {code}"
        }
    
    return {
        "code": code,
        "name": tech.name,
        "description": tech.description,
        "inoculation": {
            "mechanism": inoc["mechanism"],
            "recognition_signals": inoc["recognition_signals"],
            "defense": inoc["defense"],
            "example": inoc["example"],
        },
        "framework": "McGuire Inoculation Theory",
        "principle": "Mechanism exposure over counter-argument",
    }


def list_available() -> list[str]:
    """Return list of SCT codes with available inoculations."""
    return sorted(_INOCULATIONS.keys())


def format_inoculation(result: dict) -> str:
    """Format an inoculation result for terminal output."""
    if "error" in result:
        return f"Error: {result['error']}"
    
    if result.get("status") == "not_available":
        return f"No inoculation available for {result['code']}"
    
    inoc = result["inoculation"]
    lines = [
        f"{'=' * 60}",
        f"INOCULATION: {result['code']} -- {result['name']}",
        f"{'=' * 60}",
        "",
        "MECHANISM:",
        f"  {inoc['mechanism']}",
        "",
        "RECOGNITION SIGNALS:",
    ]
    for sig in inoc["recognition_signals"]:
        lines.append(f"  * {sig}")
    lines.extend([
        "",
        "DEFENSE:",
        f"  {inoc['defense']}",
        "",
        "EXAMPLE:",
        f"  {inoc['example']}",
        "",
        f"Framework: {result['framework']}",
        f"Principle: {result['principle']}",
        f"{'=' * 60}",
    ])
    return "\n".join(lines)
