import pytest

from app.assistant.numbers import words_to_digits


@pytest.mark.parametrize(
    ("spoken", "expected"),
    [
        (
            "Ieri am recoltat optsprezece kilograme de miere",
            "Ieri am recoltat 18 kilograme de miere",
        ),
        ("stupul doisprezece, cinci mililitri", "stupul 12, 5 mililitri"),
        ("douăzeci și cinci de mililitri", "25 de mililitri"),
        ("doi virgulă cinci litri", "2.5 litri"),
        ("două benzi de Apivar", "2 benzi de Apivar"),
        ("o sută douăzeci de grame", "120 de grame"),
        ("două sute de grame", "200 de grame"),
        ("Șaptesprezece rame", "17 rame"),
        ("optișpe kile", "18 kile"),
        ("o ramă și un stup", "o ramă și un stup"),  # articles stay
        ("hive twelve, twenty-five ml", "hive 12, 25 ml"),
        ("one hundred and five grams", "105 grams"),
        ("o sută și cinci grame", "105 grame"),
        ("hive 12, 5 ml", "hive 12, 5 ml"),  # digits untouched
        ("Stupul 7, matca văzută", "Stupul 7, matca văzută"),
    ],
)
def test_words_to_digits(spoken: str, expected: str) -> None:
    assert words_to_digits(spoken) == expected
