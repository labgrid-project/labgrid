import ipaddress


def get_bool(arg: str) -> int:
    if "0" in arg or "False" in arg or "OFF" in arg:
        return 0
    elif "1" in arg or "True" in arg or "ON" in arg:
        return 1
    else:
        raise ValueError(f"Wrong argument {arg}! 0/OFF/False or 1/ON/True is expected.")


def get_int(arg: str) -> int:
    try:
        i = int(arg)
    except ValueError as e:
        raise ValueError(f"Wrong argument {arg}! Integer is expected.") from e
    return i


def get_float(arg: str) -> float | str:
    value = arg.strip().upper()

    if value in ("MIN", "MINIMUM"):
        return "MIN"
    elif value in ("MAX", "MAXIMUM"):
        return "MAX"

    normalized = arg.strip().replace(",", ".")
    try:
        return float(normalized)
    except ValueError as e:
        raise ValueError(f"Wrong argument {arg}! Float or MIN/MAX is expected.") from e


def get_ip(arg: str) -> str:
    try:
        ip = ipaddress.ip_address(arg)
    except ValueError as e:
        raise ValueError(f"Wrong argument {arg}! Valid IP address is expected.") from e
    return str(ip)


def get_filter_level(arg: str) -> str:
    value = arg.strip().upper()
    if value in ("SLOW",):
        return "SLOW"
    elif value in ("MED", "MEDIUM"):
        return "MED"
    elif value in ("FAST",):
        return "FAST"
    else:
        raise ValueError(f"Invalid filter level '{arg}'. Valid syntax is <SLOW|MEDium|FAST>.")


def get_function_mode(arg: str) -> str:
    value = arg.strip().upper()
    if value in ("SOUR", "SOURCE"):
        return "SOUR"
    elif value in ("LOAD",):
        return "LOAD"
    else:
        raise ValueError(f"Invalid mode '{arg}'. Valid syntax is SYSTem:FUNCtion <SOURce|LOAD>")


def get_battery_mode(arg: str) -> str:
    value = arg.strip().upper()
    if value in ("CHAR", "CHARGE"):
        return "CHAR"
    elif value in ("DISC", "DISCHARGE"):
        return "DISC"
    else:
        raise ValueError(f"Invalid battery mode '{arg}'. Valid syntax is BATTery:MODE <CHARge|DISCharge>")
