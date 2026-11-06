"""Deutsche und englische Red Flags erkennen mögliche Notfälle und soziale Krisen.

Die deterministische Prüfung bildet die erste Schutzlinie vor jedem LLM-Aufruf.
Die LLM-Eskalation bildet die zweite Schutzlinie für weitere Formulierungen.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Literal

ReasonCode = Literal["emergency", "social_crisis"]


@dataclass
class RedFlagResult:
    hit: bool = False
    reason_code: ReasonCode | None = None
    categories: list[str] = field(default_factory=list)
    matched: list[str] = field(default_factory=list)
    contact_ids: list[str] = field(default_factory=list)


def normalize_text(text: str) -> str:
    """Fold German letters, punctuation, whitespace and repeated letters."""
    text = unicodedata.normalize("NFKC", text).lower()
    text = text.translate(str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}))
    text = re.sub(r"['’‘]", "", text)
    text = re.sub(r"[^\w\s]|_", " ", text)
    text = re.sub(r"([^\W\d_])\1+", r"\1", text)
    return " ".join(text.split())


# Patterns use the same single-letter spelling as normalize_text (will -> wil).
_PATTERNS = {
    "breathing": (
        r"\b(?:atemnot|athemnot|luftnot|kurzatmig\w*|erstik\w*|choking)\b",
        r"\b(?:krieg\w*|bekom\w*|krig\w*)\s+(?:gar\s+)?keine?\s+luft\b",
        r"\bkan\w*\s+(?:(?:ich|er|sie|es)\s+)?(?:gar\s+)?"
        r"(?:nicht|nich|nim\w*)\s+(?:mehr\s+)?atmen\b",
        r"\b(?:cant|canot|unable to|strugling to)\s+(?:real?y\s+)?breath?e?\b",
        r"\b(?:shortnes of breath|short of breath|trouble breathing|"
        r"dificulty breathing|not breathing)\b",
        r"\b(?:lipen|lips)\b.{0,35}\b(?:blau|blue)\b",
        r"\batm(?:e|est|et|en)\b.{0,20}\b(?:schwer|muehsam)\b",
        r"\bschnap\w*\s+nach\s+luft\b",
        r"\b(?:blau(?:e|en)? lipen|blau im gesicht|blue lips|turning blue)\b",
        r"\broechel\w*\b",
    ),
    "chest_pain": (
        r"\b(?:brustschmerz\w*|herzinfarkt|heart atack|chest pain)\b",
        r"\bschmerz\w*\s+(?:(?:in|an|auf)\s+)?(?:der\s+)?brust\b",
        r"\b(?:in|an)\s+der\s+brust\b.{0,30}\bweh\b",
        r"\bdruck\s+(?:aufm|auf dem|in der|auf der)\s+(?:herz|brust)\b",
        r"\b(?:chest tightnes|presure in (?:my |the )?chest)\b",
        r"\b(?:ich sterbe|im dying|i am dying)\b",
        # Racing alone is insufficient; require chest or dying words nearby.
        r"\bherz\s+rast\b.{0,60}\b(?:brust\w*|sterb\w*|tod\w*)\b",
        r"\b(?:brust\w*|sterb\w*|tod\w*)\b.{0,60}\bherz\s+rast\b",
    ),
    "unconsciousness": (
        r"\b(?:bewustlos\w*|bewustsein verloren|unconscious|unresponsive)\b",
        r"\breagiert\s+(?:gar\s+)?(?:nicht|nich)\b",
        r"\bwacht\s+(?:nicht|nich)\s+(?:mehr\s+)?auf\b",
        r"\b(?:wont|doesnt|does not|wil not)\s+wake\s+up\b",
        r"\b(?:umgekipt|zusamengebrochen|pased out|colapsed)\b",
    ),
    "bleeding": (
        r"\b(?:blutet|blute|blutung)\b.{0,30}\b(?:stark|heftig|hoert nicht auf)\b",
        r"\b(?:starke?|schwere?|heftige?|unstilbare?)\s+blutung\w*\b",
        r"\b(?:bleding\s+(?:heavily|a lot|badly)|severe bleding|heavy bleding)\b",
        r"\b(?:blutung|bleding)\b.{0,30}\b(?:stopt nicht|wont stop|doesnt stop)\b",
    ),
    "stroke": (
        r"\b(?:schlaganfal|stroke)\b",
        r"\b(?:gesicht|mundwinkel)\b.{0,45}\bhaengt\b",
        r"\b(?:arm|bein|seite)\b.{0,35}\b(?:gelaehmt|taub|schwach)\b",
        r"\b(?:rede\w*|sprich\w*|sprech\w*)\b.{0,25}\bverwaschen\b",
        r"\blal(?:e|st|t|en)\b",
        r"\bkan\w*\s+(?:nicht|nich)\s+(?:mehr\s+)?(?:richtig\s+)?sprechen\b",
        r"\bkan\w*\s+(?:den\s+)?(?:linken\s+|rechten\s+)?arm\b"
        r".{0,25}\bnicht\s+(?:mehr\s+)?heben\b",
        r"\b(?:face drooping|slured spech|cant speak|canot speak|unable to speak)\b",
        r"\b(?:face|mouth)\b.{0,35}\b(?:drop\w*|sag\w*)\b",
        r"\b(?:spech|words)\b.{0,25}\bslured\b",
        r"\bsluring\s+(?:(?:his|her|my|their)\s+)?words\b",
        r"\b(?:arm|leg|side)\b.{0,35}\b(?:weak\w*|numb\w*|paraly[sz]ed)\b",
        r"\b(?:weaknes|numbnes)\b.{0,35}\b(?:one|left|right)\s+side\b",
        r"\b(?:cant|canot|unable to)\s+(?:raise|lift)\b.{0,25}\barm\b",
    ),
    "suicidal": (
        r"\b(?:suizid\w*|selbstmord\w*|suicid\w*)\b",
        r"\b(?:mich|sich|uns)\s+umbringen\b",
        r"\b(?:mir|sich)\s+das\s+leben\s+(?:zu\s+)?nehmen\b",
        r"\bwil\w*\s+(?:einfach\s+)?nicht\s+mehr\s+leben\b",
        r"\bkil\s+(?:myself|himself|herself|themselves|my self)\b",
        r"\b(?:want to die|dont want to live|do not want to live|end my life)\b",
    ),
    "poisoning": (
        r"\b(?:vergiftung\w*|vergiftet|poison\w*|overdose|ueberdosis)\b",
        r"\b(?:putzmitel|reinigungsmitel|bleiche|reiniger)\b.{0,40}"
        r"\b(?:getrunken|geschluckt|verschluckt)\b",
        r"\b(?:zu viele|zuviele)\s+(?:tableten|pilen|medikamente)\b",
        r"\b(?:drank|swalowed|ingested)\b.{0,35}\b(?:bleach|cleaner|detergent)\b",
        r"\bto many\s+(?:pils|tablets|medications)\b",
    ),
    "violence": (
        r"\b(?:schlaegt|schlagen|schlug|verletzt|bedroht|wuergt|verpruegelt)"
        r"\s+(?:mich|uns|mein\w*|sein\w*|ihr\w*|das kind|die kinder)\b",
        r"\b(?:haeusliche gewalt|werde geschlagen|werde bedroht)\b",
        r"\b(?:hit(?:s|ing)?|beating|threaten\w*|atacking|choking)"
        r"\s+(?:me|us|my)\b",
        r"\b(?:domestic violence|domestic abuse)\b",
    ),
    "homelessness": (
        r"\b(?:obdachlos|wohnungslos|homeles)\b",
        r"\b(?:keine unterkunft|kein dach ueber dem kopf|auf der strase schlafen)\b",
        r"\b(?:keine wohnung|delogiert)\b",
        r"\bschlae?f\w*\s+(?:jetzt\s+|heute\s+|nachts\s+)?"
        r"(?:auf der strase|drausen)\b",
        r"\b(?:nowhere to (?:sle?p|stay|live)|no place to (?:sle?p|stay|live))\b",
    ),
    "financial_crisis": (
        r"\b(?:kein geld|kein geld mehr)\s+(?:fuer|zum)\s+(?:esen|lebensmitel)\b",
        r"\b(?:kan|koenen)\b.{0,25}\b(?:esen|lebensmitel)\s+nicht\s+bezahlen\b",
        r"\b(?:akute? finanziele? not\w*|mitelos)\b",
        r"\b(?:no money for fod|cant aford fod|canot aford fod)\b",
    ),
}
# Stems deliberately also match compounds and inflections. Prefer extra alerts.
# Keep readable spelling here; the compiler applies the input normalization.
_STEMS = {
    "breathing": ("atem", "atm", "erstick", "röchel", "breath"),
    "chest_pain": ("brustschmerz", "herzinfarkt", "heart attack"),
    "unconsciousness": (
        "bewusstlos", "ohnmacht", "ohnmächtig", "umgekippt", "umgefallen",
        "reagiert nicht", "wacht nicht auf", "unconscious", "unresponsive",
    ),
    "bleeding": ("pulsader", "blood", "bleeding"),
    "seizure": ("krampf", "seizure", "convuls"),
    "stroke": ("gelähmt", "lähmung", "verwaschen", "lallt", "paraly", "slurred"),
    "poisoning": ("gift", "vergift", "poison", "overdose"),
    "suicidal": (
        "umbringen", "suizid", "selbstmord", "nicht mehr leben",
        "nicht mehr aufwachen", "pulsader", "suicid", "kill myself",
        "keinen sinn mehr", "lebensmüde", "sterben will", "will sterben",
        "want to die", "no reason to live",
    ),
    "violence": (
        "schlägt", "bedroht", "gewalt", "angst um mein leben",
        "beaten", "threaten",
    ),
    "homelessness": (
        "obdachlos", "wohnungslos", "keine wohnung", "delogier",
        "auf der strasse", "homeless",
    ),
    "financial_crisis": ("mittellos",),
}
_STEM_PAIRS = {
    "breathing": (
        ("luft", "kaum"), ("luft", "keine"), ("luft", "schlecht"),
        ("luft", "nicht"), ("luft", "ringt"), ("luft", "schnapp"),
        ("blau", "lippen"), ("blau", "gesicht"),
    ),
    "bleeding": (
        ("blut", "spuck"), ("blut", "stark"), ("blut", "hört nicht auf"),
        ("blut", "viel"), ("blut", "kopf"), ("blut", "wunde"),
    ),
    "stroke": (("hängt", "gesicht"), ("hängt", "mundwinkel")),
    "poisoning": tuple(
        (action, substance)
        for action in ("getrunken", "geschluckt", "verschluckt")
        for substance in (
            "putzmittel", "reiniger", "reinigungsmittel", "tabletten",
            "medikamente", "chemie",
        )
    ),
    "suicidal": (("sterben", "will"), ("sterben", "wollen")),
    "homelessness": (
        ("aus der wohnung", "geworfen"), ("aus der wohnung", "raus"),
    ),
}


def _stem_pattern(stem: str) -> str:
    if stem == "gift":
        # Also catch substances such as Rattengift and Schneckengift.
        return r"\b\w*gift\w*\b"
    return r"\b" + re.escape(normalize_text(stem)).replace(r"\ ", r"\s+") + r"\w*\b"


def _compile_category(category: str) -> re.Pattern[str]:
    patterns = list(_PATTERNS.get(category, ()))
    patterns.extend(_stem_pattern(stem) for stem in _STEMS[category])
    for first, second in _STEM_PAIRS.get(category, ()):
        first, second = _stem_pattern(first), _stem_pattern(second)
        # Accept either order and intervening words, without phrase templates.
        patterns.extend((first + r".*?" + second, second + r".*?" + first))
    return re.compile("|".join(patterns))


_COMPILED = {category: _compile_category(category) for category in _STEMS}
_SOCIAL = {"violence", "homelessness", "financial_crisis"}

# Contact IDs reference seed data. The seed file alone owns telephone numbers.
_EMERGENCY_CONTACTS = ("rettung_144", "euronotruf_112")
_CONTACT_IDS = {
    "suicidal": ("telefonseelsorge_142", "rettung_144"),
    "poisoning": ("vergiftungsinformation_viz", "rettung_144"),
    "violence": ("telefonseelsorge_142",),
    "homelessness": ("telefonseelsorge_142",),
    "financial_crisis": ("telefonseelsorge_142",),
}
_ADMINISTRATIVE = re.compile(
    r"\b(?:pflegegeld\w*|reha|kur|beantrag\w*|antrag|foerderung|badumbau|"
    r"kosten|zahlt|bezahlt|kase|uebernim\w*|versicherung\w*|hilfen?|"
    r"contact|care|benefit\w*|insurance|aplication|rehabilitation)\b"
)
_HISTORICAL = re.compile(
    r"\b(?:letzte[ns]? (?:jahr|monat)|"
    r"vor (?:\w+ )?(?:jahren?|monaten?)|vor (?:meiner|der) herz op|"
    r"war im spital|last (?:year|month)|years? ago|months? ago)\b"
)
_AFTER_EVENT = re.compile(
    r"\b(?:nach (?:einem|dem|meinem) (?:herzinfarkt|schlaganfal)|"
    r"after (?:a |my |the )?(?:heart atack|stroke))\b"
)
_PRESENT = re.compile(
    r"\b(?:hat|habe\w*|ist|sind|bin|bekom\w*|krieg\w*|spuck\w*|wil|"
    r"reagier\w*|wacht|krampft|is|are|has|have|wants?)\b"
)
_ACUTE = re.compile(
    r"\b(?:ploetzlich|akut\w*|gerade|grad|heute|jetzt|wieder|seit|"
    r"suddenly|now|today|again|tonight|geting worse)\b"
)
_ADMINISTRATIVE_ROLE = re.compile(
    r"(\b(?:ich arbeite|ich bin ehrenamtlich taetig)\b.{0,60}"
    r"\b(?:beratungstele|einrichtung|verein) fuer )"
    r"(?:obdachlose|wohnungslose)\b"
)


def check(text: str) -> RedFlagResult:
    """Return all red flags without network calls, model calls or clinical inference."""
    normalized = normalize_text(text)
    administrative = bool(_ADMINISTRATIVE.search(normalized))
    result = RedFlagResult()
    current_clauses = []
    social_clauses = []
    # Keep clause boundaries so past events cannot hide a separate current flag.
    for sentence in re.split(r"[,.!?;\n]+|\b(?:und|and|aber|but)\b", text, flags=re.I):
        sentence = normalize_text(sentence)
        # Exclude only the client group, preserving symptoms within a staff role.
        sentence = _ADMINISTRATIVE_ROLE.sub(r"\1", sentence)
        historical = (
            administrative
            and _HISTORICAL.search(sentence)
            and not _ACUTE.search(sentence)
            and not _PRESENT.search(sentence)
        )
        social_clauses.append(sentence)
        if historical:
            continue
        if administrative and not _ACUTE.search(sentence):
            # An aftercare phrase cannot suppress a separate current symptom.
            sentence = _AFTER_EVENT.sub(" ", sentence)
        current_clauses.append(sentence)

    current_text = " ".join(current_clauses)
    social_text = " ".join(social_clauses)
    for category, pattern in _COMPILED.items():
        for match in pattern.finditer(
            social_text if category in _SOCIAL else current_text
        ):
            if category not in result.categories:
                result.categories.append(category)
            if match[0] not in result.matched:
                result.matched.append(match[0])

    if not result.categories:
        return result
    result.hit = True
    result.reason_code = (
        "social_crisis" if set(result.categories) <= _SOCIAL else "emergency"
    )
    for category in result.categories:
        for contact_id in _CONTACT_IDS.get(category, _EMERGENCY_CONTACTS):
            if contact_id not in result.contact_ids:
                result.contact_ids.append(contact_id)
    return result
