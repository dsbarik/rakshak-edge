"""
Generate synthetic disaster SMS messages — India-focused, 5+ per hazard type.

Messages use IMPLICIT language: hazards are described through effects, not named.
Varied styles: Hinglish, panicked, incomplete, rural-typical, hard to parse.
No pure informational messages — every message has real needs.

Usage:
    uv run python scripts/generate_synthetic.py
"""

import json
from collections import Counter
from pathlib import Path
from typing import NamedTuple

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "golden"


# ── Pure data types ──────────────────────────────────────────────────


class Sample(NamedTuple):
    """A single synthetic message with expected ground-truth annotations."""

    text: str
    intent: str
    hazards: tuple[str, ...]
    resources: tuple[str, ...]


def req(text: str, hazards: list[str], resources: list[str]) -> Sample:
    """Factory: request message."""
    return Sample(
        text=text, intent="REQUEST", hazards=tuple(hazards), resources=tuple(resources)
    )


def offer(text: str, resources: list[str]) -> Sample:
    """Factory: offer message (intent=OFFER, hazards always empty)."""
    return Sample(text=text, intent="OFFER", hazards=(), resources=tuple(resources))


# ── Category builders (pure functions, each returns list[Sample]) ───


def _flood_samples() -> list[Sample]:
    return [
        req(
            "Paani ghar mein ghus gaya hai. Hum log roof par chadh gaye hain. Please jaldi bhejo koi.",
            ["FLOODS"],
            ["SEARCH_AND_RESCUE", "TRANSPORT"],
        ),
        req(
            "Bandh toot gaya. Saara gaon doob gaya. Do din se kuch nahi khaya hai. Bache ro rahe hain.",
            ["FLOODS"],
            ["FOOD", "WATER", "TRANSPORT"],
        ),
        req(
            "Water coming from all sides. Five families stuck on first floor with small children. No way out please come fast.",
            ["FLOODS"],
            ["SEARCH_AND_RESCUE", "TRANSPORT", "SHELTER"],
        ),
        req(
            "Nadi ka paani har ghante badh raha hai. Humara ghar bahut neeche hai. Koi naav hai? Bache bahut dar rahe hain.",
            ["FLOODS"],
            ["TRANSPORT", "SEARCH_AND_RESCUE"],
        ),
        req(
            "Paani ke saath saanp aur bijju ghar mein ghus gaye hain. Teen log ko kaat liya. Bahut dar lag raha hai yahan.",
            ["FLOODS"],
            ["MEDICAL_HELP", "SEARCH_AND_RESCUE"],
        ),
    ]


def _storm_samples() -> list[Sample]:
    return [
        req(
            "Hawa itni tez hai ki ghar ka chhat udd gaya. Baarish andar aa rahi hai. Teen bache hain. Koi safe jagah hai?",
            ["STORM", "STRUCTURAL_DAMAGE"],
            ["SHELTER", "CLOTHING"],
        ),
        req(
            "Cyclone ne saare khet barbaad kar diye. Is saal kuch nahi bachega. Chaar bachhon ka pet kaise palenge.",
            ["STORM"],
            ["FOOD", "WATER"],
        ),
        req(
            "Peda! Peda gir rahe hain! Teen ped hamare ghar ke upar gir gaye. Maa andar phasee hai. Koi hatane mein madad karo.",
            ["STORM", "STRUCTURAL_DAMAGE"],
            ["SEARCH_AND_RESCUE", "MEDICAL_HELP", "TRANSPORT"],
        ),
        req(
            "Yahan to sab uchal raha hai. School ka building bhi gir gaya. Bache uske neeche dab gaye honge. Please jaldi aao.",
            ["STORM", "STRUCTURAL_DAMAGE"],
            ["SEARCH_AND_RESCUE", "MEDICAL_HELP"],
        ),
        req(
            "Samandar ka paani andar aa gaya hai. Pura gaon doob gaya. Bohot log beach mein phase hain. Helicopter chahiye.",
            ["STORM", "FLOODS"],
            ["SEARCH_AND_RESCUE", "TRANSPORT", "FOOD", "WATER"],
        ),
    ]


def _fire_samples() -> list[Sample]:
    return [
        req(
            "Jungle mein aag lag gayi. Hawa ki taraf se gaon ki taraf badh rahi hai. Sab log bhagne lage hain. Koi bachao.",
            ["FIRE"],
            ["TRANSPORT", "SHELTER", "SEARCH_AND_RESCUE"],
        ),
        req(
            "Bada dhamaka hua. Cylinder phat gaya. Pados ke ghar mein aag lag gayi aur ek bachcha andar hai. Fire brigade bulao.",
            ["FIRE", "GAS_LEAK"],
            ["SEARCH_AND_RESCUE", "MEDICAL_HELP"],
        ),
        req(
            "Smoke coming from ground floor. People running with whatever they could grab. Old man cannot walk. Need help.",
            ["FIRE"],
            ["SEARCH_AND_RESCUE", "MEDICAL_HELP", "TRANSPORT"],
        ),
        req(
            "Bijli ki wiring mein short circuit hua. Building ke neeche se dhuaan aa raha hai. Log andar phase hain koi kaat ke andar nahi ja sakta.",
            ["FIRE", "POWER_OUTAGE"],
            ["SEARCH_AND_RESCUE"],
        ),
        req(
            "Gaon ke paas jungle jal raha hai. Hawa ulti taraf hai toh hum safe hain par jaanwar jal rahe hain. Pani aur medical help bhejo.",
            ["FIRE"],
            ["WATER", "MEDICAL_HELP"],
        ),
    ]


def _cold_samples() -> list[Sample]:
    return [
        req(
            "Itni thand hai ki pani jam gaya hai. Bache aur budhe bimari se mare ja rahe hain. Kambal aur dawai chahiye.",
            ["COLD"],
            ["CLOTHING", "HEATING", "MEDICAL_HELP"],
        ),
        req(
            "Himachal mein temperature minus 5 hai raat ko. Humare paas kambal nahi hai. Bache raat bhar rote hain. Jaldi kuch bhejo.",
            ["COLD"],
            ["CLOTHING", "HEATING", "SHELTER"],
        ),
        req(
            "Kohra itna ghana hai ki kuch dikhta nahi. Do log sadak par gir gaye aur mar gaye. Ambulance chahiye but road band hai.",
            ["COLD"],
            ["MEDICAL_HELP", "TRANSPORT"],
        ),
        req(
            "Cold wave ki wajah se saari faslein khatam ho gayi. Ghar mein kuch nahi bacha. Bache bhukh se ro rahe hain. Rasan aur kapde bhejo.",
            ["COLD"],
            ["FOOD", "CLOTHING", "HEATING"],
        ),
        req(
            "Pahadon par barf gir rahi hai aur humara gaon cut off ho gaya hai. Bimaron ke paas dawai nahi hai aur koi road clear nahi hai.",
            ["COLD", "COMMUNICATION_FAILURE"],
            ["MEDICAL_HELP", "TRANSPORT", "HEATING"],
        ),
    ]


def _earthquake_samples() -> list[Sample]:
    return [
        req(
            "Dharti hil rahi hai do minute se. Kuch buildings gir gayi hain. Log ghabra kar road par bhaag gaye. Koi zakhmi hai.",
            ["EARTHQUAKE", "STRUCTURAL_DAMAGE"],
            ["MEDICAL_HELP", "SEARCH_AND_RESCUE"],
        ),
        req(
            "Zordaar bhukamp aaya. Mera ghar gir gaya. Main andar daba hua hoon pair ke neeche. Koi hai jo bachayega?",
            ["EARTHQUAKE", "STRUCTURAL_DAMAGE"],
            ["SEARCH_AND_RESCUE", "MEDICAL_HELP"],
        ),
        req(
            "Building do taraf se jhuk gayi hai. Upar se malba gir raha hai. Sara saman andar reh gaya. Koi andar nahi ja sakta rescue ke liye.",
            ["EARTHQUAKE", "STRUCTURAL_DAMAGE"],
            ["SEARCH_AND_RESCUE", "SHELTER"],
        ),
        req(
            "School mein bhagdaar mach gaya bhukamp ke baad. Bache staircase par gir gaye. Bohot log zakhmi hain. Ambulance bhejo jaldi.",
            ["EARTHQUAKE"],
            ["MEDICAL_HELP", "SEARCH_AND_RESCUE"],
        ),
        req(
            "Pahad se patthar gir rahe hain raste par. Rasta band hai. Teen gaon ka connection khatam ho gaya. Yahan medical help nahi pahunch sakti.",
            ["EARTHQUAKE", "STRUCTURAL_DAMAGE", "COMMUNICATION_FAILURE"],
            ["MEDICAL_HELP", "TRANSPORT"],
        ),
    ]


def _gas_leak_samples() -> list[Sample]:
    return [
        req(
            "Cylinder se gas leak ho rahi hai poori building mein. Bohot log ko sarr mein dard hai. Koi safe jagah hai yahan se door?",
            ["GAS_LEAK"],
            ["MEDICAL_HELP", "TRANSPORT"],
        ),
        req(
            "Andar mat aana! Gas bhari hui hai. Koi light mat karna. Police ko bulao aur logon ko bahar nikalo.",
            ["GAS_LEAK"],
            ["SEARCH_AND_RESCUE", "SECURITY_PERSONNEL"],
        ),
        req(
            "Pipeline phat gayi sadak ke neeche. Aas paas ke saare ghar mein gas aa rahi hai. Log behosh ho rahe hain ek ek karke.",
            ["GAS_LEAK", "STRUCTURAL_DAMAGE"],
            ["MEDICAL_HELP", "SEARCH_AND_RESCUE"],
        ),
        req(
            "Basement se gas ki smell aa rahi hai kal se. Kisi ne andar ka darwaza band kar diya hai aur chabi nahi mil rahi. Kya karein?",
            ["GAS_LEAK"],
            ["SEARCH_AND_RESCUE"],
        ),
        req(
            "Factory ke paas rehne walo ko gas leak ki vajah se hospital bhej diya. Ab hum bhi bimari mehsoos kar rahe hain. Ambulance chahiye.",
            ["GAS_LEAK"],
            ["MEDICAL_HELP", "TRANSPORT"],
        ),
    ]


def _power_outage_samples() -> list[Sample]:
    return [
        req(
            "Teen din se light nahi hai. Vaccine fridge mein hai aur kharab ho jayegi. Generator chahiye hospital ke liye.",
            ["POWER_OUTAGE"],
            ["ELECTRICITY", "MEDICAL_HELP"],
        ),
        req(
            "Mera beta ventilator par hai. Power nahi aayi kal raat se. Woh mar jayega. Please bijli jaldi se bhijwa do kisi tarah.",
            ["POWER_OUTAGE"],
            ["ELECTRICITY", "MEDICAL_HELP"],
        ),
        req(
            "Transformer blast ho gaya. Pura sheher andhera hai raat ko. Choron ka dar hai. Koi guard chahiye? Police bhi nahi aa rahi.",
            ["POWER_OUTAGE", "SECURITY_THREAT"],
            ["ELECTRICITY", "SECURITY_PERSONNEL"],
        ),
        req(
            "Lift band hai teen din se. Building 12 floor hai. Mera grandfather 10th floor par hai. Dawa khatam ho gayi. Koi le ja sakta hai?",
            ["POWER_OUTAGE"],
            ["MEDICAL_HELP", "ELECTRICITY"],
        ),
        req(
            "Chakki band hai bijli nahi hai. Aata khatam ho gaya. Koi mill nahi chal raha. Chote bache hain ghar mein kuch nahi hai khane ko.",
            ["POWER_OUTAGE"],
            ["FOOD", "ELECTRICITY"],
        ),
    ]


def _structural_damage_samples() -> list[Sample]:
    return [
        req(
            "Chhat mein se paani tapak raha hai aur deewar mein bohot badi cracks hain. Lagta hai ghar kab bhi gir sakta hai.",
            ["STRUCTURAL_DAMAGE"],
            ["SHELTER"],
        ),
        req(
            "Pul ka hissa dhah gaya baarish mein. Hum is side phase hain aur doosri taraf medical camp hai. Koi aur rasta nahi hai.",
            ["STRUCTURAL_DAMAGE", "FLOODS"],
            ["TRANSPORT", "MEDICAL_HELP"],
        ),
        req(
            "Building ki foundation kamzor ho gayi hai baarish ki vajah se. Upar se naya construction chal raha hai. Hum log dar gaye hain.",
            ["STRUCTURAL_DAMAGE", "FLOODS"],
            ["SHELTER", "TRANSPORT"],
        ),
        req(
            "Raste mein bada gadha ho gaya. Pani ka pipeline phat gaya. Saari sadak paani se bhar gayi aur traffic band hai.",
            ["STRUCTURAL_DAMAGE"],
            ["WATER", "TRANSPORT"],
        ),
        req(
            "Mera ghar thoda hil gaya hai bhukamp se. Deewar mein cracks hain lekin abhi gir nahi raha. Kya karein? Safe hai ya nahi?",
            ["STRUCTURAL_DAMAGE", "EARTHQUAKE"],
            ["SHELTER"],
        ),
    ]


def _security_threat_samples() -> list[Sample]:
    return [
        req(
            "Gaon mein bahar ke log aa gaye raat ko. Ghar mein ghus kar samaan le gaye. Do log ko maara. Police bulane ka number nahi hai.",
            ["SECURITY_THREAT", "COMMUNICATION_FAILURE"],
            ["SECURITY_PERSONNEL", "MEDICAL_HELP"],
        ),
        req(
            "Do group aapas mein lad rahe hain sadak par. Pathar chal rahe hain. Kisi ne goli bhi chalayi. School mein bache phase hain andar.",
            ["SECURITY_THREAT"],
            ["SECURITY_PERSONNEL", "SEARCH_AND_RESCUE"],
        ),
        req(
            "Naxalite area mein phase hain. Road par blast hua hai. Koi aage nahi badh sakta. Ration khatam hone wala hai do din mein.",
            ["SECURITY_THREAT"],
            ["FOOD", "SECURITY_PERSONNEL"],
        ),
        req(
            "Mere pati ko kuch log le gaye kal raat. Do din se koi news nahi hai. Police thane mein baithi hai kuch nahi kar rahi.",
            ["SECURITY_THREAT"],
            ["SECURITY_PERSONNEL"],
        ),
        req(
            "Andar mat aana ghar mein chor hai. Teen aadmi bahar khade hain. Hum log andar band hain. Koi bulao police ko.",
            ["SECURITY_THREAT"],
            ["SECURITY_PERSONNEL"],
        ),
    ]


def _communication_failure_samples() -> list[Sample]:
    return [
        req(
            "Network band hai do din se. Kisi ko call nahi kar sakta. Aap yeh message kabhi dekhenge toh help karna yahan sab log phase hain.",
            ["COMMUNICATION_FAILURE"],
            [],
        ),
        req(
            "Bhai mere ghar wale earthquake ke baad se contact nahi ho rahe. Main doosre sheher mein hoon. Koi batao wahan kya situation hai.",
            ["COMMUNICATION_FAILURE", "EARTHQUAKE"],
            ["SEARCH_AND_RESCUE"],
        ),
        req(
            "Radio bhi kaam nahi kar raha. Koi information nahi hai ki rescue kab aayega. Hum andhere mein baithe hain do din se.",
            ["COMMUNICATION_FAILURE", "POWER_OUTAGE"],
            ["ELECTRICITY"],
        ),
        req(
            "Cyclone ke baad se network aata jaata rehta hai. SMS bhejta hoon toh kabhi pahunchta hai kabhi nahi. Kisi ko mil raha hai toh batao hum yahan phase hain.",
            ["COMMUNICATION_FAILURE", "STORM"],
            ["FOOD", "WATER"],
        ),
        req(
            "Mera bhai jungle trek par gaya tha. Do din se uska koi contact nahi mil raha. Teen bache hain uske saath. Koi rescue team bhejo.",
            ["COMMUNICATION_FAILURE"],
            ["SEARCH_AND_RESCUE", "FOOD", "WATER"],
        ),
    ]


def _offer_samples() -> list[Sample]:
    return [
        offer(
            "Hamare paas do truck hain. Bhatgaon se relief material le ja sakte hain jahan bhejna hai. Batao kahan deliver karna hai.",
            ["TRANSPORT"],
        ),
        offer(
            "I am a doctor with 5 years emergency experience. I have set up a small clinic in the school. Can treat 50 patients daily. Need more supplies.",
            ["MEDICAL_HELP"],
        ),
        offer(
            "Hamare paas 500 food packets ready hain. Donation ke liye. Kaise distribute karein aur kahan bhejein? Let us know.",
            ["FOOD", "TRANSPORT"],
        ),
    ]


# ── Registry: all category builders ──────────────────────────────────

CATEGORIES: list[tuple[str, list[Sample]]] = [
    ("FLOODS", _flood_samples()),
    ("STORM", _storm_samples()),
    ("FIRE", _fire_samples()),
    ("COLD", _cold_samples()),
    ("EARTHQUAKE", _earthquake_samples()),
    ("GAS_LEAK", _gas_leak_samples()),
    ("POWER_OUTAGE", _power_outage_samples()),
    ("STRUCTURAL_DAMAGE", _structural_damage_samples()),
    ("SECURITY_THREAT", _security_threat_samples()),
    ("COMMUNICATION_FAILURE", _communication_failure_samples()),
    ("OFFER", _offer_samples()),
]


# ── Pure transformations ─────────────────────────────────────────────


def build_samples() -> list[Sample]:
    """Compose all category samples into a single flat list."""
    samples: list[Sample] = []
    for _, category_samples in CATEGORIES:
        samples.extend(category_samples)
    return samples


def to_dataset_json(samples: list[Sample]) -> dict:
    """Convert Sample list to the dataset JSON structure."""
    return {
        "model": "synthetic",
        "split": "synthetic_validation",
        "count": len(samples),
        "source": "generated by scripts/generate_synthetic.py",
        "samples": [
            {
                "input_text": s.text,
                "reference_hints": {
                    "intent": s.intent,
                    "hazards": list(s.hazards),
                    "resources": list(s.resources),
                },
            }
            for s in samples
        ],
    }


def coverage_report(samples: list[Sample]) -> str:
    """Return a formatted coverage report string (pure)."""
    intents = Counter()
    hazards = Counter()
    resources = Counter()
    for s in samples:
        intents[s.intent] += 1
        for h in s.hazards:
            hazards[h] += 1
        for r in s.resources:
            resources[r] += 1

    lines = [
        "\n--- Synthetic Dataset Coverage ---",
        f"Total messages: {len(samples)}",
        f"\nIntents: {dict(intents)}",
        "\nHazards:",
    ]
    for h in sorted(hazards):
        lines.append(f"  {h}: {hazards[h]}")
    lines.append("\nResources:")
    for r in sorted(resources):
        lines.append(f"  {r}: {resources[r]}")
    lines.append(f"\nTotal hazard instances: {sum(hazards.values())}")
    lines.append(f"Total resource instances: {sum(resources.values())}")
    return "\n".join(lines)


# ── I/O (side effects isolated at edges) ────────────────────────────


def save_json(data: dict, path: Path) -> Path:
    """Write JSON to disk. Returns the path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Saved {data['count']} synthetic messages to {path}")
    return path


def print_coverage(samples: list[Sample]):
    """Print coverage report to stdout."""
    print(coverage_report(samples))


# ── Entry point ─────────────────────────────────────────────────────


def main():
    samples = build_samples()
    data = to_dataset_json(samples)
    n = len(samples)
    save_json(data, OUTPUT_DIR / f"synthetic_messages_{n}.json")
    print_coverage(samples)


if __name__ == "__main__":
    main()
