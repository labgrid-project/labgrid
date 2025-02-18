from ..exception import ExecutionError
from ...util.snmp import SimpleSNMP

# Base OID for the Gude power switch as per the MIB file from gude8210
POWER_OID_BASE = "1.3.6.1.4.1.28507.1.1.2.2.1.3"
NUMBER_OF_OUTLETS = 8  # Max number of outlets from the MIB


def power_set(host, port, index, value):
    """
    Sets the power state of a specific outlet on the Gude power switch.

    Args:
        host (str): The IP address of the power switch.
        port (int or None): SNMP port, default is 161 or None.
        index (int): Outlet index.
        value (bool): True to turn on, False to turn off.
        community (str): SNMP community string.
    """
    # Validate index within allowable range
    if index is None or not (1 <= int(index) <= NUMBER_OF_OUTLETS):
        raise ExecutionError("Invalid outlet index. Ensure the index is within the range 1 to 8.")

    # Setup SNMP connection and OID for the target outlet
    _snmp = SimpleSNMP(host, 'private', port=port)
    oid = f"{POWER_OID_BASE}.{index}"
    snmp_value = "1" if value else "0"  # SNMP value for on/off

    print(f"Debug: Attempting SNMP SET on host {host}, OID {oid}, value {snmp_value}")

    try:
        # Set the power state for the specified outlet
        _snmp.set(oid, snmp_value)
        print(f"Debug: SNMP SET successful for OID {oid} with value {snmp_value}")
    except Exception as e:
        print(f"Debug: SNMP SET failed for OID {oid} with exception {e}")
        raise ExecutionError(f"Failed to set power state on outlet {index}: {e}")


def power_get(host, port, index):
    """
    Retrieves the current power state of a specific outlet on the Gude power switch.

    Args:
        host (str): The IP address of the power switch.
        port (int or None): SNMP port, default is 161 or None.
        index (int): Outlet index.
        community (str): SNMP community string.

    Returns:
        bool: True if the outlet is on, False if it's off.
    """
    # Validate index within allowable range
    if index is None or not (1 <= int(index) <= NUMBER_OF_OUTLETS):
        raise ExecutionError("Invalid outlet index. Ensure the index is within the range 1 to 8.")

    # Setup SNMP connection and OID for the target outlet
    _snmp = SimpleSNMP(host, 'public', port=port)
    oid = f"{POWER_OID_BASE}.{index}"

    print(f"Debug: Attempting SNMP GET on host {host}, OID {oid}")

    try:
        # Retrieve the current power state for the specified outlet
        value = _snmp.get(oid)
        print(f"Debug: SNMP GET returned value {value} for OID {oid}")

        # Verify and interpret the SNMP response
        if str(value).strip() == "1":
            return True  # Outlet is on
        elif str(value).strip() == "0":
            return False  # Outlet is off
        else:
            raise ExecutionError(f"Unexpected SNMP value '{value}' for outlet {index}")
    except Exception as e:
        print(f"Debug: SNMP GET failed for OID {oid} with exception {e}")
        raise ExecutionError(f"Failed to get power state for outlet {index}: {e}")
