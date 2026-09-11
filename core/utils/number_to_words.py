from decimal import Decimal, ROUND_HALF_UP

from num2words import num2words


def amount_to_words(amount: Decimal, currency_name: str = "Kwacha", subunit_name: str = "Ngwee") -> str:
    """Render a monetary amount as words for a printed receipt, e.g.
    Decimal("15360.00") -> "Fifteen thousand three hundred and sixty Kwacha"."""
    amount = Decimal(amount).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    whole = int(amount)
    cents = int((amount - whole) * 100)

    words = num2words(whole, lang='en').replace(',', '')
    words = words[0].upper() + words[1:]
    text = f"{words} {currency_name}"
    if cents:
        cents_words = num2words(cents, lang='en').replace(',', '')
        text += f" and {cents_words} {subunit_name}"
    return text
