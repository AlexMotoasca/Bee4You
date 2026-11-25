"""Spoken numbers -> digits, in plain code, before the text reaches the LLM.

Amounts are the field that must never be wrong, and LLMs miscount number words
("optsprezece" came back as 19). Speech recognizers often write numbers as words, so we
convert Romanian and English number words deterministically: "optsprezece" -> "18",
"douăzeci și cinci" -> "25", "doi virgulă cinci" -> "2.5", "twenty-five" -> "25".

Lone "un"/"o"/"una"/"one" are left alone: they are usually articles ("o ramă").
"""

import re
import unicodedata


def _plain(word: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", word.casefold()) if unicodedata.category(c) != "Mn"
    )


_UNITS = {
    # Romanian (accents stripped; colloquial short forms included)
    "zero": 0,
    "unu": 1,
    "doi": 2,
    "doua": 2,
    "trei": 3,
    "patru": 4,
    "cinci": 5,
    "sase": 6,
    "sapte": 7,
    "opt": 8,
    "noua": 9,
    "zece": 10,
    "unsprezece": 11,
    "unspe": 11,
    "doisprezece": 12,
    "douasprezece": 12,
    "doispe": 12,
    "treisprezece": 13,
    "treispe": 13,
    "paisprezece": 14,
    "patrusprezece": 14,
    "paispe": 14,
    "cincisprezece": 15,
    "cincispe": 15,
    "saisprezece": 16,
    "saispe": 16,
    "saptesprezece": 17,
    "saptispe": 17,
    "optsprezece": 18,
    "optispe": 18,
    "nouasprezece": 19,
    "nouaspe": 19,
    # English
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
}
_TENS = {
    "douazeci": 20,
    "treizeci": 30,
    "patruzeci": 40,
    "cincizeci": 50,
    "saizeci": 60,
    "saptezeci": 70,
    "optzeci": 80,
    "nouazeci": 90,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}
_HUNDRED = {"suta": 100, "sute": 100, "hundred": 100}
_ONE = {"un", "o", "una", "one", "a"}  # only count when followed by hundred/suta
_AND = {"si", "and"}
_POINT = {"virgula", "point", "punct"}

_TOKEN = re.compile(r"[\w]+|[^\w]+", re.UNICODE)


def _is_number_word(w: str) -> bool:
    return w in _UNITS or w in _TENS or w in _HUNDRED


def _parse(words: list[str]) -> tuple[int, int] | None:
    """Parse the longest number at the start of `words` (plain forms). Returns (value, used)."""
    value, i, seen = 0, 0, False
    # hundreds: "o suta", "doua sute", "one hundred", "hundred"
    if i + 1 < len(words) and (words[i] in _ONE or words[i] in _UNITS) and words[i + 1] in _HUNDRED:
        value = (1 if words[i] in _ONE else _UNITS[words[i]]) * 100
        i, seen = i + 2, True
    elif i < len(words) and words[i] in _HUNDRED:
        value, i, seen = 100, i + 1, True
    # "one hundred and five", "o suta si cinci"
    if (
        seen
        and i + 1 < len(words)
        and words[i] in _AND
        and (words[i + 1] in _TENS or words[i + 1] in _UNITS)
    ):
        i += 1
    if i < len(words) and words[i] in _TENS:
        value += _TENS[words[i]]
        i, seen = i + 1, True
        # "douazeci si cinci", "twenty five", "twenty-five"
        if i + 1 < len(words) and words[i] in _AND and words[i + 1] in _UNITS:
            value += _UNITS[words[i + 1]]
            i += 2
        elif i < len(words) and words[i] in _UNITS and _UNITS[words[i]] < 10:
            value += _UNITS[words[i]]
            i += 1
    elif i < len(words) and words[i] in _UNITS:
        value += _UNITS[words[i]]
        i, seen = i + 1, True
    return (value, i) if seen else None


def words_to_digits(text: str) -> str:
    tokens = _TOKEN.findall(text)
    word_idx = [k for k, t in enumerate(tokens) if t[0].isalnum() or t[0] == "_"]
    plain = [_plain(tokens[k]) for k in word_idx]
    out: list[str] = []
    pos = 0  # index into tokens already emitted
    w = 0
    while w < len(word_idx):
        parsed = (
            _parse(plain[w:])
            if (
                _is_number_word(plain[w])
                or (plain[w] in _ONE and w + 1 < len(plain) and plain[w + 1] in _HUNDRED)
            )
            else None
        )
        if parsed is None:
            w += 1
            continue
        value, used = parsed
        end = w + used
        number = str(value)
        # decimals: "doi virgula cinci" -> 2.5
        if end + 1 < len(plain) and plain[end] in _POINT:
            frac = _parse(plain[end + 1 :])
            if frac is not None:
                number = f"{value}.{frac[0]}"
                end += 1 + frac[1]
        start_tok, end_tok = word_idx[w], word_idx[end - 1]
        out.append("".join(tokens[pos:start_tok]))
        out.append(number)
        pos = end_tok + 1
        w = end
    out.append("".join(tokens[pos:]))
    return "".join(out)
