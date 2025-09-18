from django.apps import apps

def apply():
    M = apps.get_model("core","Member")
    f = M._meta.get_field("household_role")
    choices = list(getattr(f, "choices", []) or [])
    label = "Individueel"
    key = "individual"
    if not any(k == key or str(v).strip().lower() == label.lower() for k, v in choices):
        # voeg in vóór "other" indien aanwezig, anders achteraan
        idx = None
        for i, (k, v) in enumerate(choices):
            if k == "other":
                idx = i
                break
        if idx is None:
            choices.append((key, label))
        else:
            choices.insert(idx, (key, label))
        f.choices = tuple(choices)
