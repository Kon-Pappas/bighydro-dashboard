"""Εγγραφή JSON μόνο όταν αλλάζει το περιεχόμενο (K16, D98).

Τα παράγωγα αρχεία (υδατικό ισοζύγιο, άντληση, μονάδες, κλιματολογία, εβδομαδιαία ENTSO-E) ξαναγράφονταν σε ΚΑΘΕ run με νέα χρονοσφραγίδα, οπότε
το καθημερινό job έκανε commit ακόμη και όταν δεν είχε αλλάξει τίποτα. Εδώ το αρχείο ξαναγράφεται μόνο αν αλλάζει κάτι ΕΚΤΟΣ από τις χρονοσφραγίδες
του πρώτου επιπέδου (`Generated`, `Updated`)· έτσι η χρονοσφραγίδα σημαίνει «πότε άλλαξε τελευταία φορά το περιεχόμενο», όπως και στα αρχεία ημερών."""
import json
import os

VOLATILE = ("Generated", "Updated")


def _norm(doc):
    """Ό,τι θα γραφόταν, όπως θα διαβαζόταν ξανά (tuples -> lists, κλειδιά -> str)."""
    return json.loads(json.dumps(doc, ensure_ascii=False))


def _strip(doc, volatile):
    return {k: v for k, v in doc.items() if k not in volatile} if isinstance(doc, dict) else doc


def write_json_if_changed(path, doc, indent=None, volatile=VOLATILE):
    """Γράφει το doc στο path (ατομικά) μόνο αν διαφέρει από το υπάρχον περιεχόμενο εκτός από τις χρονοσφραγίδες.
    -> True αν γράφτηκε, False αν δεν χρειαζόταν. Ένα ελλιπές ή μη αναγνώσιμο υπάρχον αρχείο ξαναγράφεται."""
    new = _norm(doc)
    try:
        with open(path, encoding="utf-8") as f:
            old = json.load(f)
    except (OSError, ValueError):
        old = None
    if old is not None and _strip(old, volatile) == _strip(new, volatile):
        return False
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=indent)
        f.write("\n")
    os.replace(tmp, path)
    return True
